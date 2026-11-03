from app.pestinha_engine import PetNeuralSession, stimulate_session


def test_original_lif_network_has_470_neurons():
    session = PetNeuralSession("bryan")
    assert session.brain.N == 470
    assert session.brain.n_synapses > 0


def test_neural_events_return_original_motor_and_emotion_data():
    state = stimulate_session("test-session-neural", "bryan", "pet")
    assert state["engine"] == "original-pestinha-lif"
    assert state["neurons"] == 470
    assert state["emotion"] in {"observando", "contente", "feliz", "curioso", "bravo", "triste", "assustado"}
    assert state["motor"] in session_motor_names()


def session_motor_names():
    from app.pestinha_engine import PetNeuralSession
    return set(PetNeuralSession("bryan").brain.motor_names)


def test_bryan_and_jorge_have_individual_neural_parameters():
    bryan = PetNeuralSession("bryan")
    jorge = PetNeuralSession("jorge")
    assert bryan.brain.seed != jorge.brain.seed
    assert bryan.brain.temperament != jorge.brain.temperament
