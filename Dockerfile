FROM python:3.7-stretch

ENV TZ Europe/Moscow
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y --no-install-recommends \
		ffmpeg mkvtoolnix tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m user
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code/
RUN pip install -r requirements.txt
COPY . /code/
RUN chown -R user /code

USER user

VOLUME /var/lib/videodata

EXPOSE 5000
