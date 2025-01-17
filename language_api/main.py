from datetime import datetime
import logging
import os

from flask import Flask, redirect, render_template, request

from google.cloud import datastore
from google.cloud import language_v1 as language




app = Flask(__name__)


@app.route("/")
def homepage():
    # Create a Cloud Datastore client.
    datastore_client = datastore.Client()

    # # Use the Cloud Datastore client to fetch information from Datastore
    # Query looks for all documents of the 'Sentences' kind, which is how we
    # store them in upload_text()
    query = datastore_client.query(kind="Sentences")
    text_entities = list(query.fetch())

    # # Return a Jinja2 HTML template and pass in text_entities as a parameter.
    return render_template("homepage.html", text_entities=text_entities)


@app.route("/upload", methods=["GET", "POST"])
def upload_text():
    text = request.form["text"]

    # Analyse sentiment using Sentiment API call
    sentiment = analyze_text_sentiment(text)[0].get('sentiment score')
    output = gcp_analyze_entities(text=text)

    # Assign a label based on the score
    overall_sentiment = 'unknown'
    if sentiment > 0:
        overall_sentiment = 'positive'
    if sentiment < 0:
        overall_sentiment = 'negative'
    if sentiment == 0:
        overall_sentiment = 'neutral'

    # Create a Cloud Datastore client.
    datastore_client = datastore.Client()

    # Fetch the current date / time.
    current_datetime = datetime.now()

    # The kind for the new entity. This is so all 'Sentences' can be queried.
    kind = "Sentences"

    # Create the Cloud Datastore key for the new entity.
    key = datastore_client.key(kind, 'sample_task')

    # Alternative to above, the following would store a history of all previous requests as no key
    # identifier is specified, only a 'kind'. Datastore automatically provisions numeric ids.
    # key = datastore_client.key(kind)

    # Construct the new entity using the key. Set dictionary values for entity
    entity = datastore.Entity(key)
    entity["text"] = text
    entity["timestamp"] = current_datetime
    entity["sentiment"] = overall_sentiment
    entity["entity"] = output

    # Save the new entity to Datastore.
    datastore_client.put(entity)

    # Redirect to the home page.
    return redirect("/")


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

@app.route("/sentiment/<string:text>", methods=["GET", "POST"])
def analyze_text_sentiment(text):
    if request.method == "POST":
        text = str(request.form)

    client = language.LanguageServiceClient()
    document = language.Document(content=str(text), type_=language.Document.Type.PLAIN_TEXT)

    response = client.analyze_sentiment(document=document)

    sentiment = response.document_sentiment
    results = dict(
        text=text,
        score=f"{sentiment.score:.1%}",
        magnitude=f"{sentiment.magnitude:.1%}",
    )
    for k, v in results.items():
        print(f"{k:10}: {v}")

    # Get sentiment for all sentences in the document
    sentence_sentiment = []
    for sentence in response.sentences:
        item={}
        item["text"]=sentence.text.content
        item["sentiment score"]=sentence.sentiment.score
        item["sentiment magnitude"]=sentence.sentiment.magnitude
        sentence_sentiment.append(item)

    return str(sentence_sentiment)

# Entity Analysis
@app.route("/entity/<string:text>", methods=["GET", "POST"])
def gcp_analyze_entities(text, debug=0):
    """
    Analyzing Entities in a String

    Args:
      text_content The text content to analyze
    """
    if request.method == "POST":
        text = str(request.form)

    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)
    response = client.analyze_entities(document=document)
    output = []

    # Loop through entitites returned from the API
    for entity in response.entities:
        item = {}
        item["name"]=entity.name
        item["type"]=language.Entity.Type(entity.type_).name
        item["Salience"]=entity.salience

        if debug:
            print(u"Representative name for the entity: {}".format(entity.name))

            # Get entity type, e.g. PERSON, LOCATION, ADDRESS, NUMBER, et al
            print(u"Entity type: {}".format(language.Entity.Type(entity.type_).name))

            # Get the salience score associated with the entity in the [0, 1.0] range
            print(u"Salience score: {}".format(entity.salience))

        # Loop over the metadata associated with entity. For many known entities,
        # the metadata is a Wikipedia URL (wikipedia_url) and Knowledge Graph MID (mid).
        # Some entity types may have additional metadata, e.g. ADDRESS entities
        # may have metadata for the address street_name, postal_code, et al.
        for metadata_name, metadata_value in entity.metadata.items():
            item[metadata_name]=metadata_value
            if debug:
                print(u"{}: {}".format(metadata_name, metadata_value))

        # Loop over the mentions of this entity in the input document.
        # The API currently supports proper noun mentions.
        if debug:
            for mention in entity.mentions:
                print(u"Mention text: {}".format(mention.text.content))
                # Get the mention type, e.g. PROPER for proper noun
                print(
                    u"Mention type: {}".format(language.EntityMention.Type(mention.type_).name)
                )
        output.append(item)

    # Get the language of the text, which will be the same as
    # the language specified in the request or, if not specified,
    # the automatically-detected language.
    if debug:
        print(u"Language of the text: {}".format(response.language))

    return str(output)


# Content Classification
@app.route("/classify/<string:text>", methods=["GET", "POST"])
def gcp_classify_text(text):
    if request.method == "POST":
        text = str(request.form)

    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)

    response = client.classify_text(document=document)

    output = []
    for category in response.categories:
        category_output = "category=" + category.name + ", confidence="+str(category.confidence)
        output.append(category_output)

    return str(output)

# Syntax Analysis
@app.route("/syntax/<string:text>", methods=["GET", "POST"])
def gcp_analyze_syntax(text, debug=0):
    """
    Analyzing Syntax in a String

    Args:
      text The text content to analyze
    """
    if request.method == "POST":
        text = str(request.form)

    client = language.LanguageServiceClient()
    document = language.Document(content=text, type_=language.Document.Type.PLAIN_TEXT)
    response = client.analyze_syntax(document=document)

    output = []
    # Loop through tokens returned from the API
    for token in response.tokens:
        word = {}
        # Get the text content of this token. Usually a word or punctuation.
        text = token.text

        # Get the part of speech information for this token.
        # Parts of spech are as defined in:
        # http://www.lrec-conf.org/proceedings/lrec2012/pdf/274_Paper.pdf
        part_of_speech = token.part_of_speech
        # Get the tag, e.g. NOUN, ADJ for Adjective, et al.

        # Get the dependency tree parse information for this token.
        # For more information on dependency labels:
        # http://www.aclweb.org/anthology/P13-2017
        dependency_edge = token.dependency_edge

        word["word"]=text.content
        word["begin_offset"]=text.begin_offset
        word["part_of_speech"]=language.PartOfSpeech.Tag(part_of_speech.tag).name

        # Get the voice, e.g. ACTIVE or PASSIVE
        word["Voice"]=language.PartOfSpeech.Voice(part_of_speech.voice).name
        word["Tense"]=language.PartOfSpeech.Tense(part_of_speech.tense).name

        # See API reference for additional Part of Speech information available
        # Get the lemma of the token. Wikipedia lemma description
        # https://en.wikipedia.org/wiki/Lemma_(morphology)
        word["Lemma"]=token.lemma
        word["index"]=dependency_edge.head_token_index
        word["Label"]=language.DependencyEdge.Label(dependency_edge.label).name

        if debug:
            print(u"Token text: {}".format(text.content))
            print(
                u"Location of this token in overall document: {}".format(text.begin_offset)
            )
            print(
                u"Part of Speech tag: {}".format(
                    language.PartOfSpeech.Tag(part_of_speech.tag).name
                )
            )

            print(u"Voice: {}".format(language.PartOfSpeech.Voice(part_of_speech.voice).name))
            # Get the tense, e.g. PAST, FUTURE, PRESENT, et al.
            print(u"Tense: {}".format(language.PartOfSpeech.Tense(part_of_speech.tense).name))

            print(u"Lemma: {}".format(token.lemma))

            print(u"Head token index: {}".format(dependency_edge.head_token_index))
            print(
                u"Label: {}".format(language.DependencyEdge.Label(dependency_edge.label).name)
            )

        output.append(word)


    # Get the language of the text, which will be the same as
    # the language specified in the request or, if not specified,
    # the automatically-detected language.
    if debug:
        print(u"Language of the text: {}".format(response.language))
    return str(output)

if __name__ == "__main__":
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
