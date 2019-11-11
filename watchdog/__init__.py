from .workflow import Workflow, DxTask
from .wechat import WeChatSender


class WatchDog(object):
    def __init__(self):
        self.workflow = Workflow()
        self.sender = WeChatSender()

        # registry task to workflow
        self.workflow.register_task(DxTask())

    def run(self):
        reports = self.workflow.run()
        if not self.workflow.need_report:
            return
        self.sender.send_md("\n".join(reports))
