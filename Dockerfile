FROM python:3.6

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt ./

RUN pip install -r requirements.txt

COPY install/* ./
RUN pip install aiosip-0.2.0-py2.py3-none-any.whl

# Bundle app source
COPY app/ /app

EXPOSE 6100 
CMD [ "python", "server.py" ]
