
import argparse
import json

from typing import Optional, Union
from requests import Session, Response


class CommandInvokerError(Exception):
    def __init__(self, code, msg):
        super().__init__(f'{code}: {msg}')
        self.code = code
        self.msg = msg

    def __str__(self):
        return str(self.msg)


def parse_response(response: Response) -> Union[dict, None, str]:
    """
    Parses the raw response returned from a remote command invocation, returning
    its content, which is trimmed of leading and trailing whitespace.
    The input will look like the following:

    OK:\r\ntrue                                ---->  returns "true"

    or in the error case,

    "Error # :\r\nSome error string goes here  ---->  throws CommandInvokerError(#, "Some error string goes here")

    where # is the integer representing the error code returned.

    @param response - the raw response from the server
    @throws CommandInvokerError if the response from the server indicates an Error state
    @returns response from the server stripped of the protocol

    """
    status: str = ''
    code: int = 1
    result: Union[dict, None, str] = None
    try:
        response_text = response.text
        status = response_text[:response_text.index(':')].split(' ')[0]
        result = response_text[response_text.index(':') + 1:].strip()
        if status == 'Error':
            code = int(response_text[:response_text.index(':')].split(' ')[1])
        else:
            code = 0
        data_parts = {'status': status, 'code': code, 'result': result}
    except Exception:
        data_parts = {
            'status': 'Error',
            'code': code,
            'result': "Unable to parse the server's response",
        }
    if status == 'OK':
        pass
    elif status == 'Error':
        raise CommandInvokerError(code=data_parts.get('code'), msg=data_parts.get('result'))
    else:
        raise CommandInvokerError(
            code=code,
            msg=f'Unknown error occurred.  Status: ({data_parts.get("status")}) Result: {data_parts.get("result")}',
        )
    try:
        result = json.loads(result)
    except Exception as exc_json:
        pass
    return result


def main(
        domain: str,
        username: str,
        password: str,
        query_id: str,
        proxies: Optional[dict] = None,
):
    session = Session()
    session.proxies = proxies
    session.headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    token: Optional[str] = None

    def run(action: str, *args, **kwargs):
        result: Union[dict, list, None, str] = None
        try:
            # API supports positional args, but transmits them as "param1=value&param2=value..."
            pargs: dict = {f'param{index}': value for index, value in enumerate(args, start=1)}
            url_params: dict = {
                'orion.user.security.token': token,
                ':output': 'json',
                **pargs,
                **kwargs,
            }
            url: str = f'{domain}/remote/{action}'
            if action == 'core.getSecurityToken':
                response: Response = session.get(url=url, params=url_params, auth=(username, password))
            else:
                response = session.get(url=url, params=url_params)
            # We may need to add support for POST in the future
            result = parse_response(response)
        except Exception as exc_run:
            print(f'Error running ePO action "{action}": {exc_run}')
            raise exc_run
        return result

    def get_token():
        try:
            return run(action='core.getSecurityToken')
        except Exception as exc_token:
            print(f'Failed to get token: {exc_token}')
            raise exc_token

    # authenticate
    try:
        token = get_token()
    except Exception as exc_auth:
        print(f'{exc_auth}')

    def list_query_results():
        return run(action='core.executeQuery', target=query_id)

    get_token()
    return list_query_results()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--username',
        type=str,
        help='Username',
        required=True,
        default=None
    )
    parser.add_argument(
        '--password',
        type=str,
        help='Password',
        required=True,
        default=None
    )
    parser.add_argument(
        '--query_id',
        type=str,
        help='The query ID to retrieve data from',
        required=False,
        default=None
    )
    parser.add_argument(
        '--domain',
        type=str,
        help="The FQDN for your ePO server",
        required=False,
        default=''
    )
    parser.add_argument(
        '--proxies',
        type=str,
        help="JSON structure specifying 'http' and 'https' proxy URLs",
        required=False,
    )
    args = parser.parse_args()

    results = main(
        domain=args.domain,
        username=args.username,
        password=args.password,
        query_id=args.query_id,
        proxies=json.loads(args.proxies),
    )

    if results:
        for record in results:
            print(record)
    else:
        print('No results found')
