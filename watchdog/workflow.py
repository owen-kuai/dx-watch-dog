from watchdog.dx import DxChecker


class _BaseTask(object):
    def __init__(self):
        self.need_report = False

    def run(self):
        pass

    def __call__(self, *args, **kwargs):
        return self.run()


class DxTask(_BaseTask):
    def run(self):
        dx_checker = DxChecker()
        dx_checker.check()
        if not dx_checker.is_healthy:
            self.need_report = True
        return dx_checker.report


class Workflow(object):
    def __init__(self):
        self.tasks = []
        self.reports = []

        self.need_report = False

    def register_task(self, task):
        assert isinstance(task, _BaseTask)
        self.tasks.append(task)

    def run(self):
        for t in self.tasks:
            try:
                report = t()
                if t.need_report:
                    self.need_report = True
            except Exception as e:
                report = "Run task {} error: {}".format(t, e)
                self.need_report = True

            if report and isinstance(report, str):
                self.reports.append(report)

        return self.reports
