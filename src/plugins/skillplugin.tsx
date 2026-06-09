import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { ServerConnection } from '@jupyterlab/services';
import { URLExt } from '@jupyterlab/coreutils';
import { Notification } from '@jupyterlab/apputils';
import { Debouncer } from '@lumino/polling';

const PLUGIN_ID = 'jupydeep:skill';

const skillPlugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [ISettingRegistry],
  activate: async (app: JupyterFrontEnd, settingRegistry: ISettingRegistry) => {
    try {
      const skillsSettings = await settingRegistry.load(PLUGIN_ID);

      const debouncer = new Debouncer(async () => {
        const currentSettings = skillsSettings.composite;
        const serverSettings = ServerConnection.makeSettings();
        const requestUrl = URLExt.join(
          serverSettings.baseUrl,
          'jupydeep/skills'
        );
        const response = await ServerConnection.makeRequest(
          requestUrl,
          {
            method: 'POST',
            body: JSON.stringify(currentSettings)
          },
          serverSettings
        );

        if (!response.ok) {
          Notification.error('Failed to update Skills Setting on server.', {
            autoClose: 3000
          });
        } else {
          const data = await response.json();
          if (data?.status === 'success') {
            Notification.success('Congratulations: ' + (data?.message || ''), {
              autoClose: 3000
            });
          } else {
            console.log(
              'Skills setting updated on server, but intianlized failed'
            );
            Notification.error('Warning: ' + (data?.message || ''), {
              autoClose: 3000
            });
          }
        }
      }, 1200);

      skillsSettings.changed.connect(() => {
        void debouncer.invoke();
      });
    } catch (error) {
      console.error('Failed to load skills setting', error);
    }
  }
};

export default skillPlugin;
