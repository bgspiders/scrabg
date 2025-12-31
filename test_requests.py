import requests
url='https://blog.bgspider.com/'
response = requests.get(url)
print(response.status_code)
print(response.text)
