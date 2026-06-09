import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { URLExt } from '@jupyterlab/coreutils';
import { ServerConnection } from '@jupyterlab/services';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export interface IServerResponse<T = any> {
  status: 'success' | 'error' | string;
  message?: string;
  payload?: T;
}

export class SettingsSyncer {
  /**
   * Core request function: safely pushes a configuration snapshot to the specified backend endpoint
   * @param endpoint Backend route, e.g., 'jupydeep/skills'
   * @param settingsSnapshot Configuration snapshot (ISettingRegistry.IConstraints)
   * @returns Parsed backend data, or null if the request fails
   */
  static async sync(endpoint: string, settingsSnapshot: any): Promise<IServerResponse | null> {
    const serverSettings = ServerConnection.makeSettings();
    const requestUrl = URLExt.join(serverSettings.baseUrl, endpoint);

    const response = await ServerConnection.makeRequest(
      requestUrl,
      {
        method: 'POST',
        body: JSON.stringify(settingsSnapshot)
      },
      serverSettings
    );

    if (!response.ok) {
      throw response;
    }

    return await response.json();
  }
}