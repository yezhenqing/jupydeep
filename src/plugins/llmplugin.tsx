import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
//import { ServerConnection } from '@jupyterlab/services';
//import { URLExt } from '@jupyterlab/coreutils';
import { SettingsSyncer } from '../lib/utils';
import { Notification } from '@jupyterlab/apputils';
import { Debouncer } from '@lumino/polling';

const PLUGIN_ID = 'jupydeep:llm';

const llmPlugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [ISettingRegistry],
  activate: async (app: JupyterFrontEnd, settingRegistry: ISettingRegistry) => {
    try {
      const llmSettings = await settingRegistry.load(PLUGIN_ID);

      const debouncer = new Debouncer(async () => {
        const currentSettings = llmSettings.composite;
        try {
          const data = await SettingsSyncer.sync(
            'jupydeep/llm',
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
          Notification.error('Failed to update LLMs Setting on server.', {
            autoClose: 3000
          });
        }
      }, 800);

      llmSettings.changed.connect(() => {
        void debouncer.invoke();
      });
    } catch (error) {
      console.error('Failed to load llm setting', error);
    }
  }
};

export default llmPlugin;
