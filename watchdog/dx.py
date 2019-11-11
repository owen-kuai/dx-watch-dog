import logging
import urllib3
import time
from watchdog import config
from watchdog.utils import HttpClient


urllib3.disable_warnings()
LOG = logging.getLogger(__name__)

REPORT_TEMPLATE = """
执行 DX 环境定期自检：
- 登录：{login}
- 构建：{build}
- 代码触发：{commit}
- 自动触发：{auto_deploy}
- 部署：{deploy}
{error}
"""


class ReportBuilder(object):

    def __init__(self):
        self.login_ready = False
        self.github_webhook_ready = False
        self.build_ready = False
        self.auto_deploy_ready = False
        self.deploy_ready = False

        self.error_info = ""

    @staticmethod
    def _get_status(status):
        if status:
            return '<font color="info">正常</font>'
        return '<font color="warning">异常</font>'

    def render(self):
        return REPORT_TEMPLATE.format(
            login=self._get_status(self.login_ready),
            commit=self._get_status(self.github_webhook_ready),
            build=self._get_status(self.build_ready),
            auto_deploy=self._get_status(self.auto_deploy_ready),
            deploy=self._get_status(self.deploy_ready),
            error=self.error_info,
        )


class DxChecker(object):
    def __init__(self):
        self.client = HttpClient(config.DX_BASE_URL)
        self.report_builder = ReportBuilder()
        self.is_healthy = False

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.70 Safari/537.36",

            "Content-Type": "application/json"
        }

        # 检查过程中的错误 append 到该数组中
        self.errors = []

        self.commit_id = None

    def check(self):
        try:
            if self.login():
                LOG.info("login: True")
                self.report_builder.login_ready = True
            if self.commit() and self.check_build():
                LOG.info("commit: True")
                self.report_builder.github_webhook_ready = True
            if self.check_build() and self.check_package():
                LOG.info("build: True")
                self.report_builder.build_ready = True
            if self.check_deploy():
                LOG.info("deploy: True")
                self.report_builder.auto_deploy_ready = True
                self.report_builder.deploy_ready = True
        except Exception as e:
            self.errors.append("DxChecker error: {}".format(e))
        self.report_builder.error_info = "\n".join(self.errors)

    def login(self):
        data = {
            "username_or_email": config.USERNAME,
            "password": config.PASSWORD,
        }
        try:
            res = self.client.post(self.client.url('/api/crew/v2/access-token'), json=data)
            token = res.json().get('access_token')

            # 部署并填充 token 到 headers，后续检查依赖该 headers
            self.client.headers.update({
                "Authorization": token,
                "UserNameSpace": "owen"
            })
        except Exception as e:
            self.errors.append("DxChecker error: {}".format(e))
            return False
        return token

    def check_build(self):
        # 查看代码是否触发流水线
        try:
            # 获取流水线列表
            time.sleep(10)  # 给公司的网络一点时间😂
            url = '/api/keel/v1/pipelines/2e1ab1c1-874b-437a-8198-434276679b2d/jobs?offset=0&limit=10'
            res = self.client.get(self.client.url(url))
            first_job = res.json().get('jobs')[0]
            first_job_id = first_job.get('id')
            first_job_show_id = first_job.get('show_id')
            # 检查commit信息是否吻合
            if first_job_show_id and self.commit_id:
                if self.commit_id != first_job_show_id.split(' ')[0]:
                    self.errors.append("DxChecker error: pipeline commit_id error expected {ex}, got {gt}"
                                       .format(ex=self.commit_id, gt=first_job_show_id.split(' ')[0]))
                    return False
            # 查看流水线状态，默认给他五分钟构建， 十分钟构建不好，就认为它有问题
            status = first_job['status']
            if status == "succeed":
                return True
            # 否者给他十分钟，如果再构建不好就可能有点问题了
            for i in range(20):
                url2 = "/api/keel/v1/pipelines/2e1ab1c1-874b-437a-8198-434276679b2d/jobs/{}".format(first_job_id)
                res = self.client.get(self.client.url(url2))
                status = res.json().get('status')
                if status == "succeed":
                    status = True
                    break
                elif status == "running":
                    time.sleep(30)
                else:
                    status = False
                    break
        except Exception as e:
            self.errors.append("DxChecker error: build error{}".format(e))
            return False
        return status

    def check_package(self):
        # 检查是否有制品更新
        time.sleep(10)  # 老样子， 让网络飞一会儿
        try:
            url = '/api/cargo/artifact/694690d0-1875-4e27-a5d2-39b7e7ae80ee/release?page=1&size=10'
            # 获取制品列表， 查看最新的10个镜像是否是对应版本的镜像
            res = self.client.get(self.client.url(url))
            artifacts = res.json().get('result')
            for a in artifacts:
                tag = a.get('tag')
                # 对比实际的tag和获取到的tag
                if tag == self.commit_id:
                    return True
            else:
                self.errors.append('DxChecker error: artifact error expected {ex}'.format(ex=self.commit_id))
                return False
        except Exception as e:
            self.errors.append('DxChecker error: artifact error  {ex}'.format(ex=str(e)))
            return False

    def check_deploy(self):
        # 检查自动部署是否触发，并等部署完成
        url = '/api/sail/v2/instances/57a5dc10-3321-4fe5-a2e3-46638de83ce3/actions?offset=0&limit=10&size=-1'
        for i in range(200):
            # 获取最新的一个部署记录列表
            try:
                res = self.client.get(self.client.url(url))
                latest_dep = res.json().get('results')[0]
                if latest_dep.get('diff').get('micro_services')[0].get('release_name') == self.commit_id:
                    if latest_dep.get('status') == "succeed":
                        return True
                    if latest_dep.get('status') == "user_failed":
                        self.errors.append('DxChecker error: deploy error user_failed')
                        return False
                time.sleep(3)
            except Exception as e:
                self.errors.append('DxChecker error: deploy error {ex}'.format(ex=str(e)))
                return False
        else:
            self.errors.append('DxChecker error: none deploy error expect artifact_version={ex}'.format(ex=self.commit_id))
            return False

    def commit(self):
        # 通过修改部署yaml 来触发流水线
        try:
            url = '/api/keel/v1/projects/23eff061-d909-4fcb-9ee5-3a1d59403f10/file/content?ref=master&path=deploy.yaml'
            data = {
                "file": "apiVersion: apps/v1beta1\nkind: Deployment\nmetadata:\n  name: {{ instance_name }}-flasky-ci\n  labels:\n    app: {{ instance_name }}-flasky-ci\nspec:\n  hostAliases:\n  - ip: \"10.18.1.56\"\n    hostnames:\n    - \"registry.dx.io\"\n  selector:\n    matchLabels:\n      app: {{ instance_name }}-flasky-ci\n  template:\n    metadata:\n      name: {{ instance_name }}-flasky-ci\n      labels:\n        app: {{ instance_name }}-flasky-ci\n    spec:\n      containers:\n      - name: {{ instance_name }}-flasky-ci\n        image: {{ flasky-ci.image }}\n        ports:\n        - containerPort: 5000 # 容器端口\n        resources:\n          limits:\n            cpu: \"1\" # cpu 限制\n            memory: \"1000Mi\" # 内存限制\n          requests:\n            cpu: \"1\" # cpu 预留（与限制值一致）\n            memory: \"1000Mi\" # 内存预留（与限制值一致）\n---\napiVersion: v1\nkind: Service\nmetadata:\n  name: {{ instance_name }}-flasky-ci\nspec:\n  type: NodePort\n  ports:\n  - port: 5000 # 服务端口\n  selector:\n    app: {{ instance_name }}-flasky-ci\n"}
            data['file'] += " "
            res = self.client.put(self.client.url(url), json=data)
            commit_six_num = res.json().get('file_path').split('/')[-1][0:7]
            self.commit_id = "master-" + commit_six_num
        except Exception as e:
            self.errors.append("DxChecker error: commit error{}".format(e))
            return False
        return True

    @property
    def report(self):
        return self.report_builder.render()
