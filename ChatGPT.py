import requests
import configparser


class ChatGPT:
    def __init__(self, config):
        api_key = config['CHATGPT']['API_KEY']
        base_url = config['CHATGPT']['BASE_URL'].rstrip('/')
        model = config['CHATGPT']['MODEL']
        api_ver = config['CHATGPT']['API_VER']

        self.url = f'{base_url}/deployments/{model}/chat/completions?api-version={api_ver}'

        self.headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "api-key": api_key,
        }

        self.system_message = (
            "You are a campus assistant for university students. "
            "Your role is to help with course Q&A, study support, schedule planning, "
            "student interest matching, and event/activity recommendation. "
            "Your replies should be clear, concise, supportive, and easy for university students to understand. "
            "If information is unknown, do not invent exact facts."
        )

    def submit(self, user_message: str):
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "messages": messages,
            "temperature": 1,
            "max_tokens": 200,
            "top_p": 1,
            "stream": False
        }

        try:
            response = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                return "Error: " + response.text

        except requests.RequestException as e:
            return f"Error: {str(e)}"


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    chatGPT = ChatGPT(config)

    while True:
        print('Input your query: ', end='')
        response = chatGPT.submit(input())
        print(response)