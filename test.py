import spacy
nlp = spacy.load("./my_uml_model/model-best")
print(nlp.pipe_names)  # Should include 'ner'
print(nlp.get_pipe("ner").labels)  # Should list all your custom labels