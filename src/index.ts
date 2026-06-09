import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import '../style/index.css';
import { ILabShell } from '@jupyterlab/application';
import { ChatWidget } from './widgets/ChatWidget';

import globalPlugin from './plugins/globalplugin';
import agentPlugin from './plugins/agentplugin';
import mcpPlugin from './plugins/mcpplugin';
import llmPlugin from './plugins/llmplugin';
import skillPlugin from './plugins/skillplugin';

const PLUGIN_ID = 'jupydeep:main';

const mainPlugin: JupyterFrontEndPlugin<void> = {
  id: PLUGIN_ID,
  description: 'A JupyterLab extension for jupydeep with native AI powered.',
  autoStart: true,
  requires: [ILabShell],
  activate: async (app: JupyterFrontEnd, labShell: ILabShell) => {
    // keep this line untouched for ui-test
    console.log('JupyterLab extension JupyDeep is activated!');

    const chatWidget = new ChatWidget();
    labShell.add(chatWidget, 'right', { rank: 1000 });
  }
};

const plugins: JupyterFrontEndPlugin<any>[] = [
  llmPlugin,
  globalPlugin,
  mcpPlugin,
  skillPlugin,
  agentPlugin,
  mainPlugin
];

export default plugins;
