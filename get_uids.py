import requests, re
for q in ["433", "473", "429"]:
    r = requests.get(f'https://www.dtcbusroutes.in/bus/search/?q={q}')
    urls = set(re.findall(r'href="(/bus/route/[^"]+)"', r.text))
    print(f'{q}:', urls)
