// Configurações de interface
const uiConfig = {
    loadConfig: async () => {
        const response = await fetch('/api/config');
        const config = await response.json();
        uiConfig.applyConfig(config);
    },

    applyConfig: (config) => {
        if (config.navBar) {
            document.getElementById('main-nav').style.position = config.navBar.position;
            document.getElementById('main-nav').style.backgroundColor = config.navBar.backgroundColor;
        }
        
        if (config.theme) {
            document.body.style.backgroundColor = config.theme.backgroundColor;
            document.body.style.color = config.theme.textColor;
            document.body.style.fontSize = config.theme.fontSize + 'px';
        }
    },

    saveConfig: async (config) => {
        await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
    }
};

// Carregar configurações ao iniciar
document.addEventListener('DOMContentLoaded', uiConfig.loadConfig);
