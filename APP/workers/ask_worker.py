from PyQt6.QtCore import QThread, pyqtSignal

from LLM import LLMSession, LLMRequest, LLMResponse

class AskWorker(QThread):
    """Выполняет session.ask() вне GUI-потока."""

    done = pyqtSignal(str)     # успешный ответ
    failed = pyqtSignal(str)   # текст ошибки

    def __init__(self, session: LLMSession, request: LLMRequest, parent=None):
        super().__init__(parent)
        self._session = session
        self._request = request

    def run(self) -> None:
        try:
            response = self._session.ask(request=self._request)
            self.done.emit(response.answer)
        except Exception as exc:            # ловим всё, чтобы не уронить поток
            self.failed.emit(str(exc))