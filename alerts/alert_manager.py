from enum import Enum
from datetime import datetime

class AlertLevel(Enum):
    LOW = "baixo"
    MEDIUM = "médio"
    HIGH = "alto"

class AlertManager:
    def __init__(self):
        self.alerts = []
    
    def create_alert(self, equipment_id, message, level: AlertLevel):
        alert = {
            'timestamp': datetime.now(),
            'equipment_id': equipment_id,
            'message': message,
            'level': level
        }
        self.alerts.append(alert)
        self._notify(alert)
    
    def _notify(self, alert):
        # Implementar notificações (email, SMS, etc)
        pass
