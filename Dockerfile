FROM python:3.6-alpine
RUN mkdir /dx-watch-dog
WORKDIR /dx-watch-dog
COPY ./requirements.txt /dx-watch-dog
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y ca-certificates curl supervisor  nginx vim
COPY .vimrc /root
COPY . /captain
CMD ["python", "/captain/runner.py"]
