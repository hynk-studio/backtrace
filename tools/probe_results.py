"""Collect independent free checks without mistaking partial passes for readiness."""


class ProbeResults:
    def __init__(self, stages):
        self.stages, self.failed = stages, []

    def run(self, name, operation):
        try:
            result = operation()
            entry = result if isinstance(result, dict) else {'status': 'PASS'}
            if entry.get('status', 'PASS') != 'PASS':
                self.failed.append(name)
            self.stages[name] = entry
            return result
        except Exception as error:
            self.failed.append(name)
            self.stages[name] = {'status': 'FAIL', 'failure': {
                'error_type': type(error).__name__,
                'exit_code': getattr(error, 'returncode', None)}}
            return None

    @property
    def status(self):
        return 'FAIL' if self.failed else 'PASS'
