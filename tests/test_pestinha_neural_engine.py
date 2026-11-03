from app.pestinha_engine import PetNeuralSession, get_session_state, stimulate_session


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



def test_neural_state_can_be_read_without_creating_a_session():
    session_id = "test-session-read-only-state"
    assert get_session_state(session_id, "bryan") is None

    stimulate_session(session_id, "bryan", "activity")
    state = get_session_state(session_id, "bryan")

    assert state is not None
    assert state["neurons"] == 470
    assert state["engine"] == "original-pestinha-lif"
