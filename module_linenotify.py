import requests

TOKEN_LINENOTIFY = 'PecjRRWnVa44ckFhrBmhkH3kn73F2Rb5O3wR01GEHuL'
API_LINENOTIFY = 'https://notify-api.line.me/api/notify'


class LineNotifier():
    def __init__(self) -> None:
        self.headers = {'Authorization': f'Bearer {TOKEN_LINENOTIFY}'}

    def notify(self, str_msg) -> None:
        data = {'message': str_msg}
        requests.post(
            API_LINENOTIFY,
            headers=self.headers,
            data=data)


def notify_simple(str_msg):
    headers = {'Authorization': f'Bearer {TOKEN_LINENOTIFY}'}
    data = {'message': str_msg}
    requests.post(
        API_LINENOTIFY,
        headers=headers,
        data=data)


if __name__ == "__main__":
    notify_simple("test_message")
