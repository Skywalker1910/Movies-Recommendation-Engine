import os
from dotenv import load_dotenv

load_dotenv()  # load .env before any other import resolves env vars

from app import create_app

env = os.environ.get("FLASK_ENV", "development")

# 'application' is the conventional name for AWS Elastic Beanstalk / some PaaS
application = create_app(env)

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = env == "development"
    application.run(host="0.0.0.0", port=port, debug=debug)

