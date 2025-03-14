const configManager = {
    plcList: [],
    databaseConnections: [],

    addNewPLC: () => {
        const plc = {
            id: Date.now(),
            name: '',
            ip: '',
            tags: []
        };
        configManager.plcList.push(plc);
        configManager.renderPLCList();
    },

    addNewDatabase: () => {
        const connection = {
            id: Date.now(),
            type: '',
            connection_string: '',
            name: ''
        };
        configManager.databaseConnections.push(connection);
        configManager.renderDatabaseConnections();
    },

    saveConfig: async () => {
        const config = {
            plc: configManager.plcList,
            databases: configManager.databaseConnections,
            ui: {
                navPosition: document.getElementById('nav-position').value,
                themeColor: document.getElementById('theme-color').value
            }
        };

        await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar configurações
    fetch('/api/config')
        .then(response => response.json())
        .then(config => {
            configManager.plcList = config.plc || [];
            configManager.databaseConnections = config.databases || [];
            configManager.renderAll();
        });
});
