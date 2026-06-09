import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { SettingsSyncer } from '../lib/utils';
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
        try {
          const data = await SettingsSyncer.sync(
            'jupydeep/mcp',
            currentSettings
          );

          if (data?.status === 'success') {
            Notification.success('Success: ' + (data?.message || ''), {
              autoClose: 3000
            });
          } else {
            Notification.error('Warning: ' + (data?.message || ''), {
              autoClose: 3000
            });
          }
        } catch (error) {
          Notification.error('Failed to update MCPs Setting on server.', {
            autoClose: 3000
          });
        }
      }, 1200);

      mcpSettings.changed.connect(() => {
        void debouncer.invoke();
      });
    } catch (error) {
      console.error('Failed to load mcp setting', error);
    }
  }
};

export default mcpPlugin;
