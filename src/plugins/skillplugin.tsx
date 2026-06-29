import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { SettingsSyncer } from '../lib/utils';
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
        try {
          const data = await SettingsSyncer.sync(
            'jupydeep/skills',
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
          Notification.error('Failed to update Skills Setting on server.', {
            autoClose: 3000
          });
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
