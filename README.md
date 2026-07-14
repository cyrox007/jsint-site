# Urn of Thought))
## Системные требования (Requirement)
* Python 3.8+
* SQLite3
## Подготовка виртуальной среды проекта (Prepare project virtual environment):
### Настройка SSH-соединения для получения файлов проекта
Для начала нужно сгенерировать специальный SSH ключ, чтобы сделать это, в консоли надо ввести следующую команду:
``` console
cd ~/.ssh && ssh-keygen -t rsa
```
Нас интересует файл id_rsa. 
* Если вы работаете под OS MS Windows, то этот файл будет находиться по пути C:\Users\Имя пользователя\.ssh. Этот файл нужно открыть любым приложением для чтение и редактирования текста, и скопировать содержимое. Для этой цели подойдет программа "Блокнот" или "Notepat++". 
* Если вы пользователь ОС Linux, то для получения ключа необходимо в терминале ввести след. команду.
``` console
cat ~/.ssh/id_rsa.pub
```
Затем возьмите SSH-ключ из id_rsa.pub и поместите в конфигурацию SSH в Git. Для большего понимания вы можете посмотреть видео - https://www.youtube.com/watch?v=KqzVaUTCPbQ&t=80s 

``` bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Создание папки проекта
Создайте и перейдите в общую папку проекта в удобном для вас месте.
``` console
mkdir ~/Project && cd ~/Project
```
Клонируйте содержимое репозитория в папку. Затем вы должны создать виртуальное окружение. 
``` console
python3 -m venv venv
```
Активируйте виртуальную среду и перейдите в папку с файлами.
``` console
source venv/bin/activate && cd ~/Project/project
```
Установите требуемые библиотеки.
``` console
pip install -r requirements.txt
```
## Подключение базы данных SQLite3
В этой версии приложения в качестве базы данных используеться SQLite3. 
``` bash 
python ./db_create.py
```
## Запуск проекта 
Находясь в папке с проектом, и активированным виртуальным окружением выполните следующую команду:
``` console
export FLASK_APP=app
export FLASK_ENV=development
flask run
```
Если ошибок не будет, в консоле будет выведен адрес и порт сервера. Его нужно ввести в адресную строку браузера для перехода на веб приложение.
The launch methods known to me
``` bash
flask --app app --debug run
```
or from file
``` bash
python ./run_server.py
```
migration
``` bash 
alembic revision --message="Initial" --autogenerate
```
``` bash 
alembic upgrade head
```