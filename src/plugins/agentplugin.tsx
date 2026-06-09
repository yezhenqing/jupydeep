import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { IFormRendererRegistry } from '@jupyterlab/ui-components';
import { SettingsSyncer } from '../lib/utils';
import { Notification } from '@jupyterlab/apputils';
import { Debouncer } from '@lumino/polling';
import { queryClient, fetchEngine } from '../hooks/useEngine';
import AgentsField from './AgentsField';
import { QueryClientProvider } from '@tanstack/react-query';

const PLUGIN_ID = 'jupydeep:agent';

interface IAgentConfig {
  $ref: string;
  title: string;
  description: string;
  enabled: boolean;
  model: string;
  deep_mcps: string[];
  deep_skills: string[];
  capabilities: string[];
}

interface IAgentProps {
  [agentName: string]: IAgentConfig;
}

const agentPlugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  autoStart: true,
  requires: [ISettingRegistry, IFormRendererRegistry],
  activate: async (
    app: JupyterFrontEnd,
    settingRegistry: ISettingRegistry,
    formRegistry: IFormRendererRegistry
  ) => {
    let engineInfo: any = null;
    try {
      engineInfo = await queryClient.ensureQueryData({
        queryKey: ['engine-catalog'],
        queryFn: fetchEngine
      });
    } catch (error) {
      console.warn(
        '[JupyDeep] Failed to fetch engine catalog for settings dynamically.'
      );
      engineInfo = { payload: { mcps: [], skills: [], agents: {} } };
    }

    settingRegistry.transform(PLUGIN_ID, {
      fetch: (plugin: ISettingRegistry.IPlugin): ISettingRegistry.IPlugin => {
        const schema = JSON.parse(JSON.stringify(plugin.schema));

        // 2. Dynamically inject MCP enum values
        const availableMCPs = engineInfo?.payload?.mcps?.length
          ? engineInfo.payload.mcps
          : ['N/A'];
        if (schema.definitions?.AgentConfig?.properties?.deep_mcps?.items) {
          schema.definitions.AgentConfig.properties.deep_mcps.items.enum =
            availableMCPs;
        }

        // 3. Dynamically inject Skill enum values
        const availableSkills = engineInfo?.payload?.skills?.length
          ? engineInfo.payload.skills
          : ['N/A'];
        if (schema.definitions?.AgentConfig?.properties?.deep_skills?.items) {
          const oldEnum =
            schema.definitions.AgentConfig.properties.deep_skills.items.enum ||
            [];
          schema.definitions.AgentConfig.properties.deep_skills.items.enum = [
            ...new Set([...oldEnum, ...availableSkills])
          ];
        }

        // 4. Initialize agents
        if (schema.properties?.agents) {
          const initProps: IAgentProps = {};

          const backendAgents = engineInfo?.payload?.agents || {};
          Object.entries(backendAgents).forEach(
            ([agentName, agentData]: [string, any]) => {
              initProps[agentName] = {
                $ref: '#/definitions/AgentConfig',
                title: agentName,
                description:
                  agentData?.description || `Configuration for ${agentName}`,
                enabled: agentData?.enabled ?? true,
                model: agentData?.model || '',
                deep_mcps: Array.isArray(agentData?.deep_mcps)
                  ? agentData.deep_mcps
                  : [],
                deep_skills: Array.isArray(agentData?.deep_skills)
                  ? agentData.deep_skills
                  : [],
                capabilities: Array.isArray(agentData?.capabilities)
                  ? agentData.capabilities
                  : []
              };
            }
          );
          schema.properties.agents.properties = initProps;
        }

        return { ...plugin, schema };
      }
    });

    formRegistry.addRenderer(`${PLUGIN_ID}.agents`, {
      fieldRenderer: props => {
        return (
          <QueryClientProvider client={queryClient}>
            <AgentsField {...props} />
          </QueryClientProvider>
        );
      }
    });

    try {
      const agentSetting = await settingRegistry.load(PLUGIN_ID);

      const debouncer = new Debouncer(async () => {
        const currentSettings = agentSetting.composite || {};
        try {
          const data = await SettingsSyncer.sync(
            'jupydeep/agents',
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
          Notification.error('Failed to update Agent Setting on server.', {
            autoClose: 3000
          });
        }
      }, 1200);

      agentSetting.changed.connect(() => {
        void debouncer.invoke();
      });
    } catch (error) {
      console.error('Failed to load agent setting', error);
    }
  }
};

export default agentPlugin;
