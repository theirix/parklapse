# parklapse


A simple service for making timelapses and archiving from a RTSP stream.
Initially written for archiving camera recordings for a park.

## Architecture

There are several components of the server:

- RTSP receiver saves ten-minutes chunks (`receive_task` celery task).

- Web service provides access to stored timelapses files and to statistics.

- Timelapse assembler (`timelapse_task`) makes 60x timelapses from raw files.
Three-hourly timelapses
are produced by concatenating chunks and then by recoding them.
Daily timelapses are concatenated from hourly chunks without recoding.

- Archive task finds old chunks and recodes them to hourly
videos (slightly compressed but with 1x speed).
They are copied to temporary directory and possibly uploaded to AWS S3.

- Cleanup task (`cleanup_task`) removes old archives from a temporary directory.

- Watchdog task (`watchdog_task`) checks if the RTSP receiver is okay.
Sometimes it stucks and needed to be restarted (using kill or celery cancel).


## Deployment using Docker

Service is best launched using Docker.
Callee must provide a large directory for videodata (`VIDEODATA` compose env var). 
 
- Copy a configuration `app.env.example` to `app.env`

- Adjust configuration (consult `app/config.py` for possible parameters)

- Create required host directories at `/path/to/videodata`

      mkdir /path/to/videodata/{raw,timelapse,archive,damaged,tmp}

- Run containers:

      VIDEODATA=/path/to/videodata docker-compose up 

- Check it

      curl localhost:5000/api/stats
      
- Run a reverse proxy that proxies API calls to `/api` endpoint to the Flask web server
and data calls to `TIMELAPSES_URL_PREFIX` endpoint to the static files.