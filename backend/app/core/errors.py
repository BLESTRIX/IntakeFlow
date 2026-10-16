class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status


def require(condition, code, message, status=400):
    if not condition:
        raise DomainError(code, message, status)
