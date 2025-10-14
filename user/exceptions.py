from rest_framework.views import exception_handler

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, list):
            response.data = {"detail": response.data[0]}
        elif "detail" not in response.data:
            response.data = {"detail": "Request could not be processed."}
    return response
