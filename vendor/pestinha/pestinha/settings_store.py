"""
SETTINGS STORE - as permissões da sessão, em um lugar só.

O dicionário é o mesmo objeto para todo mundo que o lê (app, controladores,
tela inicial). Cada mudança é gravada na hora, então uma queda não perde nada.
"""

from . import config


class SettingsStore:
    """Guarda as permissões em memória e grava em disco quando elas mudam."""
    def __init__(self, paths):
        """Carrega as permissões salvas (ou o padrão)."""
        self.paths = paths
        self.perms = config.load_permissions(paths)

    def __getitem__(self, key):
        """Lê uma permissão pelo nome: store['memes']."""
        return self.perms[key]

    def update(self, new):
        """Aplica um conjunto completo de permissões (como a tela inicial envia)."""
        self.perms.update(config.permissoes_validas(new))
        self.save()

    def save(self):
        """Grava as permissões em disco (erro de disco não derruba o app)."""
        try:
            config.save_permissions(self.paths, self.perms)
        except OSError as error:
            from .log import log
            log(f"[permissões] não gravou: {error}")

    def panic(self):
        """Desliga o pet pelo pânico; vale na sessão mesmo se o disco falhar."""
        self.perms["ativo"] = False              # vale na sessão mesmo se o disco falhar
        try:
            self.save()
        except OSError as error:
            from .log import log
            log(f"[pânico] não gravou a permissão: {error} (desligado nesta sessão mesmo assim)")
