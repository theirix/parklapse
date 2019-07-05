# parklapse

- Copy a configuration `app.env.example` to `app.env`

- Adjust configuration (consult `app/config.py` for possible parameters)

- Create required host directories at `/path/to/videodata`

      mkdir /path/to/videodata/{raw,timelapse,archive,damaged,tmp}

- Run containers:

      VIDEODATA=/path/to/videodata docker-compose up 

- Check it

      curl localhost:5000/api/stats