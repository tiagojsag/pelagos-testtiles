FROM python:2.7

RUN mkdir /app
WORKDIR /app

RUN pip install vectortile
RUN pip install click

