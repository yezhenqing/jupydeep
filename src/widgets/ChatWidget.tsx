import { ReactWidget } from '@jupyterlab/ui-components';
import { LabIcon } from '@jupyterlab/ui-components';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient, closeSSE } from '../hooks/useEngine';

import prozenSvgstr from '../../style/icons/prozen.svg';
//import githubSvgstr from '../../style/icons/github.svg';
import { Shimmer } from '../components/ai-elements/shimmer';

const prozenIcon = new LabIcon({
  name: 'jupydeep:prozen',
  svgstr: prozenSvgstr
});

//const githubIcon = new LabIcon({
//  name: 'jupydeep:github',
//  svgstr: githubSvgstr
//});

import ChatBot from '../components/chat/ChatBot';

const ChatPanel = (): JSX.Element => {
  return (
    <div
      style={{
        padding: '5px',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        boxSizing: 'border-box'
      }}
    >
      <p
        style={{
          marginTop: '2px',
          opacity: 0.8,
          backgroundColor: 'var(--jp-layout-color2)',
          borderColor: 'var(--jp-border-color1)'
        }}
        className="flex items-center justify-center gap-1 border-2 rounded-full 
                   p-1 flex-nowrap whitespace-nowrap max-w-full overflow-hidden"
      >
        <Shimmer
          className="text-[var(--jp-ui-font-color3)] text-xs"
          duration={1.2}
          spread={0.25}
        >
          JupyDeep: Your AI partner in Jupyter
        </Shimmer>
        <a
          href="https://github.com/yezhenqing/jupydeep"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--jp-ui-font-color1)] hover:opacity-70 
                     inline-flex items-center justify-center flex-shrink-0"
          title="View on GitHub"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            className="w-[1rem] h-[1rem] flex-shrink-0"
            fill="currentColor"
          >
            <path d="M10.226 17.284c-2.965-.36-5.054-2.493-5.054-5.256 0-1.123.404-2.336 1.078-3.144-.292-.741-.247-2.314.09-2.965.898-.112 2.111.36 2.83 1.01.853-.269 1.752-.404 2.853-.404 1.1 0 1.999.135 2.807.382.696-.629 1.932-1.1 2.83-.988.315.606.36 2.179.067 2.942.72.854 1.101 2 1.101 3.167 0 2.763-2.089 4.852-5.098 5.234.763.494 1.28 1.572 1.28 2.807v2.336c0 .674.561 1.056 1.235.786 4.066-1.55 7.255-5.615 7.255-10.646C23.5 6.188 18.334 1 11.978 1 5.62 1 .5 6.188.5 12.545c0 4.986 3.167 9.12 7.435 10.669.606.225 1.19-.18 1.19-.786V20.63a2.9 2.9 0 0 1-1.078.224c-1.483 0-2.359-.808-2.987-2.313-.247-.607-.517-.966-1.034-1.033-.27-.023-.359-.135-.359-.27 0-.27.45-.471.898-.471.652 0 1.213.404 1.797 1.235.45.651.921.943 1.483.943.561 0 .92-.202 1.437-.719.382-.381.674-.718.944-.943"></path>
          </svg>
        </a>
      </p>

      <div
        style={{
          marginTop: '6px',
          padding: '6px',
          border: '1px dashed var(--jp-border-color1)',
          flex: 1, // Grow to fill available space
          minHeight: 0, // Enable shrinking for overflow support
          display: 'flex',
          flexDirection: 'column'
        }}
        className="rounded-lg border-dashed border-gray-400"
      >
        <div className="h-full w-full flex-1 flex flex-col min-h-0">
          <ChatBot />
        </div>
      </div>
    </div>
  );
};

export class ChatWidget extends ReactWidget {
  constructor() {
    super();
    this.id = 'jupyter-excalidraw-agents';
    this.addClass('jp-excalidraw-container');

    this.title.label = '';
    this.title.icon = prozenIcon;
    this.title.closable = true;
  }

  render(): JSX.Element {
    return (
      <QueryClientProvider client={queryClient}>
        <ChatPanel />
      </QueryClientProvider>
    );
  }

  dispose(): void {
    if (this.isDisposed) {
      return;
    }
    closeSSE();
    queryClient.clear();
    super.dispose();
  }
}

export default ChatWidget;
