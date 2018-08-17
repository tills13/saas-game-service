FROM python:3.7-alpine3.8

LABEL ImageBaseName=saas-manager

ADD . /code

WORKDIR /code

RUN apk add --update --no-cache build-base linux-headers pcre-dev
RUN pip install -r requirements.txt
RUN apk del build-base linux-headers pcre-dev
RUN echo $PG_VERSION

EXPOSE 3001
