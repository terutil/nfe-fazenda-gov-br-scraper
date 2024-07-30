import time
import requests
import re
import random
from browserforge.headers import HeaderGenerator
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Change this
api_key = ""
proxy = ''
chave_acesso = ''

good_count = 0
bad_count = 0

def format_proxy(px: str):
    try:
        if '@' not in px:
            sp = px.split(':')
            if len(sp) == 4:
                px = f'{sp[2]}:{sp[3]}@{sp[0]}:{sp[1]}'
        return {"http": f"http://{px}", "https": f"http://{px}"}
    except Exception as e:
        logging.error("Error in format_proxy: %s", str(e))
        return {}

def generate_number():
    try:
        number_length = 44
        number = ''.join(str(random.randint(0, 9)) for _ in range(number_length))
        return number
    except Exception as e:
        logging.error("Error in generate_number: %s", str(e))
        return ''
    

def get_token():
    try:
        logging.info("Creating task for HCaptcha")
        data = {
            "clientKey": api_key,
            "task": {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": "https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=resumo&tipoConteudo=7PhJ%20gAVw2g=",
                "websiteKey": "e72d2f82-9594-4448-a875-47ded9a1898a"
            }
        }
        res = requests.post('https://api.capsolver.com/createTask', json=data)
        resp = res.json()
        task_id = resp.get('taskId')
        if not task_id:
            logging.error("No taskId obtained: %s", res.text)
            return None, None

        data = {
            "clientKey": api_key,
            "taskId": task_id
        }
        while True:
            time.sleep(1)
            logging.info("Polling for task result")
            response = requests.post('https://api.capsolver.com/getTaskResult', json=data)
            resp = response.json()
            status = resp.get('status', '')
            if status == "ready":
                token = resp['solution']['gRecaptchaResponse']
                useragent = resp['solution']['userAgent']
                logging.info("HCaptcha solved successfully")
                return token, useragent
            if status == "failed" or resp.get("errorId"):
                logging.error("Failed to solve HCaptcha: %s", response.text)
                return None, None
    except Exception as e:
        logging.error("Error in get_token: %s", str(e))
        return None, None


def get_parameters():
    try:
        logging.info("Fetching parameters from the website")
        resp = requests.get("https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=resumo&tipoConteudo=7PhJ%20gAVw2g=", proxies=format_proxy(proxy))
        cookies = resp.cookies.get_dict()
        html_content = resp.text

        viewstate = re.search(r'id="__VIEWSTATE" value="([^"]+)"', html_content).group(1)
        viewstategenerator = re.search(r'id="__VIEWSTATEGENERATOR" value="([^"]+)"', html_content).group(1)
        eventvalidation = re.search(r'id="__EVENTVALIDATION" value="([^"]+)"', html_content).group(1)

        return viewstate, viewstategenerator, eventvalidation, cookies
    except Exception as e:
        logging.error("Error in get_parameters: %s", str(e))
        return None, None, None, None

def verify_token(viewstate, viewstategenerator, eventvalidation, token, userAgent, cookies, chave_acesso):
    global good_count, bad_count
    try:
        headers = HeaderGenerator()
        headers_generated = dict(headers.generate(user_agent=userAgent))
        
        data = {
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstategenerator,
            '__EVENTVALIDATION': eventvalidation,
            'ctl00$ContentPlaceHolder1$txtChaveAcessoResumo': chave_acesso,
            'h-captcha-response': token,
            'ctl00$ContentPlaceHolder1$btnConsultarHCaptcha': 'Continuar',
            'hiddenInputToUpdateATBuffer_CommonToolkitScripts': '1',
        }
        
        url = 'https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=resumo&tipoConteudo=7PhJ+gAVw2g%3d'
        logging.info("Verifying token")
        resp = requests.post(url, headers=headers_generated, data=data, cookies=cookies, proxies=format_proxy(proxy))

        if 'Falha na valida' in resp.text:
            bad_count += 1
            logging.info(f"Validation failed: Total good: {good_count} / Total bad: {bad_count}")
        else:
            good_count += 1
            logging.info(f"Validation succeeded: Total good: {good_count} / Total bad: {bad_count}")
    except Exception as e:
        logging.error("Error in verify_token: %s", str(e))

def main():
    while True:
        if(chave_acesso == ''):
            logging.error("Chave de acesso não configurada")
            chave_acesso = generate_number()
            logging.error(f"Chave de acesso gerada: {chave_acesso}")
        try:
            logging.info("Starting new iteration")
            parameters = get_parameters()
            if not all(parameters):
                logging.warning("Failed to get parameters")
                continue

            viewstate, viewstategenerator, eventvalidation, cookies = parameters
            token, userAgent = get_token()
            if not token:
                logging.warning("Failed to get token")
                continue

            verify_token(viewstate, viewstategenerator, eventvalidation, token, userAgent, cookies, chave_acesso)
        except Exception as e:
            logging.error("Error in main loop: %s", str(e))

if __name__ == "__main__":
    main()
