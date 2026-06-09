import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { ServerConnection } from '@jupyterlab/services';
import { URLExt } from '@jupyterlab/coreutils';
import { Notification } from '@jupyterlab/apputils';
import { Debouncer } from '@lumino/polling';

const PLUGIN_ID = 'jupydeep:mcp';

const mcpPlugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [ISettingRegistry],
  activate: async (app: JupyterFrontEnd, settingRegistry: ISettingRegistry) => {
    try {
      const mcpSettings = await settingRegistry.load(PLUGIN_ID);

      const debouncer = new Debouncer(async () => {
        const currentSettings = mcpSettings.composite;
        const serverSettings = ServerConnection.makeSettings();
        const requestUrl = URLExt.join(serverSettings.baseUrl, 'jupydeep/mcp');
        const response = await ServerConnection.makeRequest(
          requestUrl,
          {
            method: 'POST',
            body: JSON.stringify(currentSettings)
          },
          serverSettings
        );

        if (!response.ok) {
          Notification.error('Failed to update MCP Setting on server.', {
            autoClose: 3000
          });
        } else {
          Notification.success(
            'Congratulations, MCP setting updated on server successfully.',
            { autoClose: 3000 }
          );
        }
      }, 800);

      mcpSettings.changed.connect(() => {
        void debouncer.invoke();
      });
    } catch (error) {
      console.error('Failed to load mcp setting', error);
    }
  }
};

export default mcpPlugin;
