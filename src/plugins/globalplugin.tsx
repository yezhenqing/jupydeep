import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { IFormRendererRegistry } from '@jupyterlab/ui-components';
import { SettingsSyncer } from '../lib/utils';
import { Notification } from '@jupyterlab/apputils';
import { Debouncer } from '@lumino/polling';
import { queryClient } from '../hooks/useEngine';
import { QueryClientProvider } from '@tanstack/react-query';
import GlobalField from './GlobalField';

const PLUGIN_ID = 'jupydeep:global';

const globalPlugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [ISettingRegistry, IFormRendererRegistry],
  activate: async (
    app: JupyterFrontEnd,
    settingRegistry: ISettingRegistry,
    formRegistry: IFormRendererRegistry
  ) => {
    try {
      const globalSetting = await settingRegistry.load(PLUGIN_ID);

      formRegistry.addRenderer(`${PLUGIN_ID}._root`, {
        fieldRenderer: props => {
          return (
            <QueryClientProvider client={queryClient}>
              <GlobalField {...props} />
            </QueryClientProvider>
          );
        }
      });

      const debouncer = new Debouncer(async () => {
        const currentSettings = globalSetting.composite?._root || {};
        try {
          const data = await SettingsSyncer.sync(
            'jupydeep/global',
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
          Notification.error('Failed to update Global Setting on server.', {
            autoClose: 3000
          });
        }
      }, 1200);

      globalSetting.changed.connect(() => {
        void debouncer.invoke();
      });
    } catch (error) {
      console.error('Failed to load global setting', error);
    }
  }
};

export default globalPlugin;
