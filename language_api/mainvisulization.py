from datetime import datetime
import logging
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt,mpld3

from flask import Flask, redirect, render_template, request


app = Flask(__name__)


@app.route("/")
def visulizationpage():
    # Create a Cloud Datastore client.
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)

    weather = pd.read_csv('SampleData_Weather.csv')
    print(weather)

    weather.plot(kind='line', y='Tmax', x='Month')
    mpld3.show()

    # # Return a Jinja2 HTML template and pass in text_entities as a parameter.
    return render_template("visulization.html")


@app.errorhandler(500)
def server_error(e):
    logging.exception("An error occurred during a request.")
    return (
        """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(
            e
        ),
        500,
    )

if __name__ == "__main__":
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
