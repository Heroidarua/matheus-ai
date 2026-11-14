"""
CANTINHO DO CASTIGO - uma plaquinha de cartoon que você arrasta para onde quiser. Se você
solta o pet na frente dela, ele fica preso ali: quieto no começo, depois olha para você,
vira de costas, cola cartazes e tenta fugir. Os protestos de greve ficam suspensos enquanto
ele está lá.

O que ele faz vem da rede: o neurônio CARTAZ dispara a vontade de colar cartaz, o FUGIR
dispara quando a frustração passa do limiar, e o WATCH e o ANGRY decidem se ele olha para
você ou vira de costas. Cada fuga bem-sucedida fica salva e entra na rede como memória
(LEMBRA_FUGA), que aumenta a excitação de FUGIR. Tudo é reversível: tirar o pet do canto
ou desligar a opção no menu devolve ele à tela normal.
"""

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen

from ..core.protesto import load_signs
from ..ajustes import CARGA_FUGA_HZ_S, GANHO_CARTAZ, LIMIAR_FUGA_HZ
from ..log import log
from ..mathutil import valor_real
from ..store import read_json, write_json
from ..world.arrastavel import FloatingWidget
from ..world.cartazes import SignThing

TEXTO_PLAQUINHA = "CANTINHO\nDO CASTIGO"
PLAQUINHA_W, PLAQUINHA_H = 190, 150     # placa com as pernas
CONTORNO = QColor("#222222")
TEMPO_FUGA = 30.0             # s até a fuga virar "tentativa que não deu certo"
ALTURA_CANTO = 240            # px a partir da base da placa que contam como canto
FOLGA_BASE = 40               # px abaixo da base da placa que ainda contam (ele pousa um pouco abaixo)
MARGEM_FUGA = 40              # px para fora do canto que contam como fuga
INTERVALO_TOPO = 0.25         # s entre um "o pet à frente da placa" e outro
OLHAR_HZ = 3.0                # WATCH acima disso: ele olha para você
COSTAS_HZ = 3.0               # ANGRY acima disso: ele vira de costas para a parede
ESPERA_POUSO = 3.0            # s: soltou no ar, ainda vale entrar no castigo se pousar no canto
LIMIAR_PERDAO_HZ = 12.0       # ACEITAR acima disso: ele aceita o castigo e sai sozinho (sem contar fuga)
RANCOR_SOBE_S = 120.0         # s preso até o rancor chegar ao máximo
RANCOR_DESCE_S = 600.0        # s solto para o rancor sumir
RECEIO_POR_FALHA = 0.3        # quanto cada fuga desfeita aumenta o receio
RECEIO_DESCE_S = 1800.0       # s para o receio sumir
JANELA_RECAPTURA = 60.0       # s: devolvido ao canto até aqui depois de fugir, a fuga "deu errado"
JANELA_CASTIGO_ENSINA = 20.0  # s: a travessura feita até aqui antes do castigo é a que ele aprende a evitar
DURACAO_PUNICAO = 1.0         # s de recompensa negativa na rede ao ser preso
PUNICAO = -1.0                # recompensa durante esse tempo (o carinho vale +1)
RAIO_VISITA = 160.0           # px: cursor perto assim dele preso conta como visita
TAU_VISITA = 1.0              # s para a visita subir ou cair
DISTANCIA_PLACA = 260.0       # px: carregado perto assim da placa, a pista da placa liga
DISTANCIA_AVISO = 500.0       # px: o aviso da placa (PLACA) é forte perto dela e some a esta distância
CARTAZ_MIN_S = 8.0            # s mínimos com o mesmo cartaz antes de trocar
MEMORIA_POR_FUGA = 0.2        # quanto cada fuga que deu certo aumenta a memória (LEMBRA_FUGA)


class PlaquinhaCanto(FloatingWidget):
    """A placa de cartoon. Arrasta-se como os outros painéis e lembra onde ficou."""

    def __init__(self, app):
        """Placa 'CANTINHO DO CASTIGO' no canto da tela; começa no canto inferior esquerdo e pode ser arrastada."""
        screen = QGuiApplication.primaryScreen().availableGeometry()
        padrao = (screen.x() + 10, screen.bottom() - PLAQUINHA_H + 1)
        super().__init__(app, "castigo", "Cantinho do castigo", (PLAQUINHA_W, PLAQUINHA_H),
                         (PLAQUINHA_W, PLAQUINHA_H), padrao)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    def paintEvent(self, _event):
        """Desenha a placa com pernas e o texto (cores e tamanho fixos)."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        placa = QRectF(8, 8, w - 16, 100)
        p.setPen(QPen(CONTORNO, 5, Qt.SolidLine, Qt.RoundCap))         # pernas
        p.drawLine(QPointF(45, 104), QPointF(34, h - 4))
        p.drawLine(QPointF(w - 45, 104), QPointF(w - 34, h - 4))
        p.setPen(QPen(CONTORNO, 4))
        p.setBrush(QColor("#ffd84d"))
        p.drawRoundedRect(placa.translated(4, 5), 12, 12)               # sombra
        p.drawRoundedRect(placa, 12, 12)
        p.setPen(QColor("#c0392b"))
        area = placa.adjusted(8, 6, -8, -6)
        tamanho = 16
        while tamanho > 7 and QFontMetrics(QFont("Arial Black", tamanho)).boundingRect(
                area.toRect(), Qt.AlignCenter | Qt.TextWordWrap, TEXTO_PLAQUINHA).height() > area.height():
            tamanho -= 1
        p.setFont(QFont("Arial Black", tamanho))
        p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, TEXTO_PLAQUINHA)
        p.end()


class CastigoController:
    """Cantinho do castigo: prende o pet numa placa quando ele está muito irritado ou quando você o solta ali. Aprende com as fugas (rancor, receio, memória de fuga)."""
    def __init__(self, app, debug):
        """Guarda o estado do castigo (rancor, receio, fugas) carregado de pets/<pet>/castigo.json."""
        self.app = app
        self.path = app.pet_paths.castigo
        self.behavior = app.behavior
        self.debug = debug
        data = read_json(self.path, default={})
        vitorias = data.get("vitorias", {}) if isinstance(data, dict) else {}
        try:
            fugas = valor_real(vitorias.get("fugir", 0.0), 0.0, 1e9)
        except (TypeError, ValueError, AttributeError):
            fugas = 0.0                             # estado ilegível: começa sem fugas registradas
        self.vitorias = {"fugir": fugas}            # fugas que deram certo
        self.rancor = self._fracao(data, "rancor")   # 0..1: tempo de castigo acumulado (decai devagar)
        self.receio = self._fracao(data, "receio")   # 0..1: fugas desfeitas (inibe a fuga)
        self.visita = 0.0             # 0..1: você está perto dele enquanto está preso
        self.punicao_ate = 0.0        # até quando a rede recebe a recompensa negativa do castigo
        self.ultima_fuga_em = None    # quando a última fuga deu certo (para saber se foi desfeita)
        self.ultimo = None            # quando a última decisão foi tomada (para medir o tempo entre elas)
        self.ativo = False
        self.plaquinha = None
        self.cartaz = None
        self.dentro = False           # o pet está preso no canto agora
        self.entrou = 0.0
        self.proxima = 0.0
        self.modo = "quieto"
        self.zona_fuga = None         # (x0, x1) do canto no começo da fuga: mover a placa não vale vitória
        self.fuga_para_direita = True  # para que lado é "dentro da tela" (só esse lado conta como fuga)
        self.fuga = None              # quando ele começou a fugir (None se não está fugindo)
        self.estado = None            # PetState do pet: soltar ou prender mexe nele
        self.segurado = False         # estava sendo arrastado no quadro anterior
        self.vontade_fuga = 0.0       # 0..1: carga do disparo de FUGIR acima do limiar; cheia, ele foge
        self.cartaz_desde = 0.0       # quando o cartaz atual subiu
        self.visivel = True           # o pet está na tela (a placa só aparece junto)
        self.entrada_pendente = None  # soltou no ar: espera o pouso para decidir (até quando vale)
        self.ultimo_topo = -1e9

    @staticmethod
    def _fracao(data, chave):
        """Lê uma fração de 0 a 1 do arquivo salvo; valor inválido vira 0 (nunca derruba o app)."""
        try:
            return valor_real(data.get(chave, 0.0), 0.0, 1.0) if isinstance(data, dict) else 0.0
        except (TypeError, ValueError):
            return 0.0

    @property
    def fuga(self):
        """Quando a fuga começou (None: não está fugindo)."""
        return self._fuga

    @fuga.setter
    def fuga(self, inicio):
        # a zona é registrada quando a fuga começa: mover a placa depois não conta como fuga
        """Quando começou a fuga em andamento (None se ele não está fugindo)."""
        self._fuga = inicio
        if inicio is None:
            self.zona_fuga = None
        elif self.plaquinha is not None:
            x0 = self.plaquinha.x()
            self.zona_fuga = (x0, x0 + self.plaquinha.width())
            centro_tela = QGuiApplication.primaryScreen().availableGeometry().center().x()
            self.fuga_para_direita = (x0 + self.plaquinha.width() / 2) < centro_tela   # foge para dentro da tela

    # ---------------- menu e cena ----------------

    def toggle(self, bounds):
        """Liga ou desliga o cantinho: mostra a placa e prende/solta o pet conforme o estado."""
        self.ativo = not self.ativo
        if self.ativo:
            self._mostrar_plaquinha()
        else:
            self._soltar(self.estado)
            self._cancelar_fuga()
            if self.plaquinha is not None:
                self.plaquinha.hide()
        if self.debug():
            log(f"[castigo] {'ligado' if self.ativo else 'desligado'}")

    def set_visible(self, visible):
        """Mostra ou esconde a placa junto com o pet (a placa espera escondida, sem ser desligada)."""
        self.visivel = visible
        if self.plaquinha is not None:
            self.plaquinha.setVisible(visible and self.ativo)

    def pausar(self, state):
        """Escondeu o pet (ou pânico): ele sai do canto e uma fuga em andamento é cancelada."""
        if self.dentro:
            self._soltar(state)
        self._cancelar_fuga()

    def _mostrar_plaquinha(self):
        """Cria a placa na primeira vez e a mostra (ou deixa escondida, se o pet estiver escondido)."""
        if self.plaquinha is None:
            self.plaquinha = PlaquinhaCanto(self.app)
        self.plaquinha.setVisible(self.visivel)        # escondido ou desligado, a placa espera

    def _zona(self, bounds):
        """Caixa do canto: a largura da placa, da base dela até ALTURA_CANTO para cima (segue a placa)."""
        _left, _top, _right, bottom = bounds
        x0 = self.plaquinha.x()
        base = min(bottom, self.plaquinha.y() + self.plaquinha.height() + FOLGA_BASE)
        return x0, x0 + self.plaquinha.width(), base - ALTURA_CANTO, base

    def _no_canto(self, body, bounds):
        """Diz se o pet está dentro da área do canto (perto da placa, na base da tela)."""
        if self.plaquinha is None:
            return False
        x0, x1, y0, y1 = self._zona(bounds)
        return x0 <= body.x <= x1 and y0 <= body.y <= y1

    # ---------------- a cada quadro ----------------

    def sinais(self, body=None):
        """O que o cantinho manda para a rede neste momento."""
        placa = 0.0
        if self.ativo and self.plaquinha is not None and self.plaquinha.isVisible():
            if self.dentro or body is None:
                placa = 1.0
            else:                                    # aviso: forte perto da placa, some longe dela
                c = self.plaquinha.geometry().center()
                placa = max(0.0, 1.0 - math.hypot(body.x - c.x(), body.y - c.y()) / DISTANCIA_AVISO)
        return {
            "PRESO": 1.0 if self.dentro else 0.0,
            "LEMBRA_FUGA": self.memoria_fuga(),
            "PLACA": placa,
            "VISITA": self.visita if self.dentro else 0.0,
            "RECEIO": self.receio,
            "RANCOR": self.rancor,
        }

    def perto_da_placa(self, body):
        """Pista do condicionamento: você está carregando ele perto da placa."""
        if not self.ativo or self.plaquinha is None or not body.held:
            return False
        g = self.plaquinha.geometry()
        return math.hypot(body.x - g.center().x(), body.y - g.center().y()) < DISTANCIA_PLACA

    def punicao(self, now):
        """Recompensa negativa para a rede logo depois de ser preso (o castigo ensina)."""
        return PUNICAO if now < self.punicao_ate else 0.0

    def tick_lento(self, dt):
        """Rancor sobe preso e cai solto; receio cai devagar."""
        if self.dentro:
            self.rancor = min(1.0, self.rancor + dt / RANCOR_SOBE_S)
        else:
            self.rancor = max(0.0, self.rancor - dt / RANCOR_DESCE_S)
        self.receio = max(0.0, self.receio - dt / RECEIO_DESCE_S)

    def deslocar(self, segundos):
        """A pausa não conta: os prazos do cantinho andam junto com ela."""
        if self._fuga is not None:
            self._fuga += segundos
        for nome in ("entrada_pendente", "ultima_fuga_em"):
            if getattr(self, nome) is not None:
                setattr(self, nome, getattr(self, nome) + segundos)
        self.punicao_ate += segundos
        self.cartaz_desde += segundos
        self.entrou += segundos
        if self.ultimo is not None:
            self.ultimo += segundos

    def memoria_fuga(self):
        """0..1 para a rede (LEMBRA_FUGA): cada fuga que deu certo deixa a fuga mais fácil."""
        return min(1.0, MEMORIA_POR_FUGA * self.vitorias["fugir"])

    def act(self, now, body, bounds, cursor, state, motores, asleep=False):
        """Um passo do castigo a cada tick: prende/solta, controla fugas e cartazes, e atualiza o rancor."""
        dt = min(0.5, now - self.ultimo) if self.ultimo is not None else 0.0
        self.ultimo = now
        self.estado = state
        solto = self.segurado and not body.held        # acabou de ser solto
        self.segurado = body.held
        if not self.ativo:
            return
        self._checar_fuga(now, body)
        if solto:
            self.entrada_pendente = now + ESPERA_POUSO  # pode estar no ar: decide quando pousar
        if body.held:
            self.entrada_pendente = None
        no_canto = self._no_canto(body, bounds) and body.grounded
        if not self.dentro:
            if self.entrada_pendente is not None and body.grounded:
                if no_canto and now <= self.entrada_pendente:   # você o deixou no canto
                    self._entrar(now, state)
                self.entrada_pendente = None
            elif self.entrada_pendente is not None and now > self.entrada_pendente:
                self.entrada_pendente = None
            return
        if not no_canto or body.held:
            self._soltar(state)
            return
        state.castigo = True
        perto = math.hypot(cursor[0] - body.x, cursor[1] - body.y) < RAIO_VISITA
        self.visita += ((1.0 if perto else 0.0) - self.visita) * min(1.0, dt / TAU_VISITA)
        if now - self.ultimo_topo >= INTERVALO_TOPO:   # ele fica na frente da placa
            self.app.pet.raise_()
            self.ultimo_topo = now
        self._posicionar_cartaz(body)
        if not asleep:                                 # dormindo, ele não cola cartaz nem foge
            self._decidir(now, dt, body, bounds, motores)
        if self.dentro:
            self._aplicar(body, cursor, state, bounds, motores)

    def _entrar(self, now, state):
        """Prende o pet no canto: ele fica parado, sem poder sair até ser solto ou perdoado."""
        self.estado = state
        self.dentro = True
        self.vontade_fuga = 0.0
        self.entrou = now
        self.visita = 0.0
        state.castigo = True
        self.punicao_ate = now + DURACAO_PUNICAO
        if self.fuga is not None:
            # pego no meio de uma tentativa de fuga: a tentativa acaba e conta como fuga que deu errado
            self._cancelar_fuga()
            self.receio = min(1.0, self.receio + RECEIO_POR_FALHA)
        if self.ultima_fuga_em is not None and now - self.ultima_fuga_em < JANELA_RECAPTURA:
            # devolvido ao canto logo depois de fugir: a fuga deu errado
            self.vitorias["fugir"] = max(0.0, self.vitorias["fugir"] - 1.0)
            self.receio = min(1.0, self.receio + RECEIO_POR_FALHA)
            self.ultima_fuga_em = None
            self.salvar()
            if self.debug():
                log(f"[castigo] fuga desfeita: receio {self.receio:.2f}")
        memoria = getattr(self.app, "memory", None)
        if memoria is not None:
            memoria.punir(now, JANELA_CASTIGO_ENSINA)
        condicionamento = getattr(self.app, "conditioning", None)
        if condicionamento is not None:
            condicionamento.outcome(now, cues=("PLACA",))
        if self.debug():
            log("[castigo] entrou no canto")

    def _decidir(self, now, dt, body, bounds, motores):
        """
        Perdão: ACEITAR acima do limiar, ele sai sozinho (sem contar fuga) e o rancor cai pela metade.
        Cartaz: sorteio com a frequência do disparo de CARTAZ. Fuga: quando FUGIR passa do limiar.
        """
        if motores.get("ACEITAR", 0.0) >= LIMIAR_PERDAO_HZ:
            self.rancor *= 0.5
            self._soltar(self.estado)
            if self.debug():
                log(f"[castigo] aceitou e saiu (ACEITAR {motores['ACEITAR']:.1f} Hz)")
            return
        cartaz_novo = self.cartaz is None or now - self.cartaz_desde >= CARTAZ_MIN_S
        if cartaz_novo and random.random() < motores.get("CARTAZ", 0.0) * GANHO_CARTAZ * dt:
            self._soltar_cartaz()
            bravo = motores.get("ANGRY", 0.0) >= COSTAS_HZ
            textos = self.xingamentos if bravo and random.random() < 0.7 else self.cartazes + self.xingamentos[:2]
            self.cartaz = SignThing(random.choice(textos), "castigo")
            self._posicionar_cartaz(body)              # já nasce em cima dele
            self.cartaz_desde = now
            self.cartaz.show()
            if self.debug():
                log("[castigo] colou um cartaz")
        fugir = motores.get("FUGIR", 0.0)
        self.vontade_fuga = max(0.0, self.vontade_fuga + dt * (fugir - LIMIAR_FUGA_HZ) / CARGA_FUGA_HZ_S)
        if self.vontade_fuga >= 1.0:                   # vontade sustentada, não um pico
            if self.debug():
                log(f"[castigo] tentou fugir (FUGIR {fugir:.1f} Hz, vontade cheia)")
            self._iniciar_fuga(now, bounds)

    def _iniciar_fuga(self, now, bounds):
        """Começa uma fuga para o lado de dentro da tela; se der certo, o pet sai do canto."""
        x0, x1, _y0, _y1 = self._zona(bounds)
        left, _top, right, _bottom = bounds
        para_direita = (x0 + x1) / 2 < (left + right) / 2   # foge para o lado de dentro da tela
        destino = max(left + 60, min(right - 60, x1 + 300 if para_direita else x0 - 300))
        self.fuga = now
        self.fuga_para_direita = para_direita
        self._soltar(self.estado)
        self.behavior.fuga_alvo = destino
        self.behavior.walk_to(destino, 160.0)          # o primeiro passo é na hora

    def _cancelar_fuga(self):
        """Cancela a fuga em andamento (ele volta a ser contido)."""
        self.fuga = None
        self.behavior.fuga_alvo = None

    def _checar_fuga(self, now, body):
        """Vitória só se ele saiu andando, dentro do prazo, da zona onde estava preso."""
        if self.fuga is None:
            return
        if now - self.fuga > TEMPO_FUGA or body.held:  # prazo vencido, ou você o carregou
            self._cancelar_fuga()
            return
        if self.zona_fuga is None:                  # sem placa não há canto de onde fugir
            self._cancelar_fuga()
            return
        x0, x1 = self.zona_fuga
        saiu = body.x > x1 + MARGEM_FUGA if self.fuga_para_direita else body.x < x0 - MARGEM_FUGA
        if saiu:
            self.vitorias["fugir"] += 1.0
            self.ultima_fuga_em = now
            self._cancelar_fuga()
            self.salvar()
            if self.debug():
                log(f"[castigo] fugiu! vitórias de fuga: {self.vitorias['fugir']:.0f}")

    def salvar(self):
        """Grava as vitórias. Falha de disco não derruba o quadro; tenta de novo ao salvar o app."""
        try:
            write_json(self.path, {"vitorias": self.vitorias, "rancor": self.rancor, "receio": self.receio})
        except OSError as error:
            log(f"[castigo] não gravou as vitórias: {error}")

    def _aplicar(self, body, cursor, state, bounds, motores):
        """Aplica no corpo o que o canto pede: parar de frente ou de costas para a parede, e o olhar."""
        if motores.get("ANGRY", 0.0) >= COSTAS_HZ:
            left, _top, right, _bottom = bounds
            state.gaze = (-1.0 if body.x - left < right - body.x else 1.0, 0.0)   # de costas: olha a parede mais perto
        elif motores.get("WATCH", 0.0) >= OLHAR_HZ:
            dx, dy = cursor[0] - body.x, cursor[1] - body.y
            dist = math.hypot(dx, dy) or 1.0
            state.gaze = (dx / dist, dy / dist)                  # olha para você
        else:
            state.gaze = (0.0, 0.9)                              # quieto, olhando para baixo

    @property
    def cartazes(self):
        """Seção [castigo] do cartazes.txt do pet (ou as neutras). Relida a cada cartaz: dá para editar com ele aberto."""
        return tuple(load_signs(self.app.conteudo.signs)["castigo"])

    @property
    def xingamentos(self):
        """Frases de xingamento (símbolos) da seção [xingamento] do cartazes.txt do pet."""
        return tuple(load_signs(self.app.conteudo.signs)["xingamento"])

    def _posicionar_cartaz(self, body):
        """Prende o cartaz no pet: o cartaz sempre fica em cima dele, acompanhando o movimento."""
        if self.cartaz is None:
            return
        _ex, ey = body.extents()
        self.cartaz.place(body.x, body.y - ey - self.cartaz.height() / 2 + 8)
        self.cartaz.update()

    def _soltar_cartaz(self):
        """Tira o cartaz do cantinho (fecha a janela e libera a memória)."""
        if self.cartaz is not None:
            self.cartaz.close()
            self.cartaz.deleteLater()
            self.cartaz = None

    def _soltar(self, state=None):
        """Solta o pet do canto e zera a vontade de fugir."""
        self.dentro = False
        self.vontade_fuga = 0.0
        self.entrada_pendente = None
        self.punicao_ate = 0.0                       # saiu do canto: a recompensa negativa acaba junto
        if state is not None:
            state.castigo = False
        self._soltar_cartaz()
