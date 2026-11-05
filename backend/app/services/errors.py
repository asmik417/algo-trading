"""Errors services raise instead of HTTP exceptions, so services stay usable from jobs and scripts.
main.py maps them to the contract's status codes: BadInput 400, NotFound 404, Conflict 409.
"""


class ServiceError(Exception):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class BadInput(ServiceError):
    status_code = 400


class NotFound(ServiceError):
    status_code = 404


class Conflict(ServiceError):
    status_code = 409
