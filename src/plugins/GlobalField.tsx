import React from 'react';
import { FieldProps } from '@rjsf/utils';
import { useEngineCatalog, useMlflowTest } from '../hooks/useEngine';

interface IGlobalConfig {
  default_agent?: string;
  default_model?: string;
  usage_limit_usd?: number | null;
  request_limit?: number | null;
  total_tokens_limit?: number | null;
  tool_timeout?: number;
  backend?: string;
  enable_system_mlflow?: boolean;
  mlflow_tracking_uri?: string;
}

const EMPTY_ARRAY: any[] = [];

const GlobalField: React.FC<FieldProps> = props => {
  const { formData = {}, onChange, disabled, readonly } = props;
  const config = formData as IGlobalConfig;

  const { data: engineData } = useEngineCatalog();
  const llmsEnum = engineData?.payload?.llms || EMPTY_ARRAY;
  const agentsEnum = Object.keys(engineData?.payload?.agents ?? {});

  const is_mlflow_active = engineData?.payload?.is_mlflow_active || false;

  const handleChange = (field: keyof IGlobalConfig, value: any) => {
    onChange({
      ...config,
      [field]: value
    });
  };

  const backendOptions = [
    'LocalBackend',
    'StateBackend',
    'DockerSandbox',
    'CompositeBackend'
  ];

  const mlflowTestMutation = useMlflowTest();
  // Handler function triggered by the Test button
  const handleTestConnection = () => {
    mlflowTestMutation.mutate(
      { tracking_uri: config.mlflow_tracking_uri || 'http://127.0.0.1:5000' },
      {
        // Optional callback handlers if needed
        onError: error => {
          console.error('MLflow connection test failed:', error);
        },
        onSuccess: d => {}
      }
    );
  };

  return (
    <div className="mb-5 font-sans">
      <div className="mb-4 pb-2 border-b-2 border-[var(--jp-border-color2)]">
        <h3 className="text-lg font-semibold text-[var(--jp-ui-font-color1)] m-0">
          Global Configuration
        </h3>
      </div>

      {/* Default Agent */}
      <div className="mb-4">
        <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
          Default Agent ID
        </label>
        <select
          className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
          value={config.default_agent || ''}
          onChange={e => handleChange('default_agent', e.target.value)}
          disabled={disabled || readonly}
        >
          <option value="" disabled selected style={{ display: 'none' }}>
            Select agent...
          </option>
          {agentsEnum.map((m: string) => (
            <option key={m} value={`${m}`}>
              {m}
            </option>
          ))}
        </select>
      </div>

      {/* Default Model */}
      <div className="mb-4">
        <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
          Default Model
        </label>
        <select
          className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
          value={config.default_model || ''}
          onChange={e => handleChange('default_model', e.target.value)}
          disabled={disabled || readonly}
        >
          <option value="" disabled>
            Select model...
          </option>
          {llmsEnum.map((m: string) => (
            <option key={m} value={`${m}`}>
              {m}
            </option>
          ))}
        </select>
      </div>

      {/* Usage Limits Section */}
      <div className="mb-4">
        <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
          Usage Limits
        </label>

        {/* Budget Limit (USD) */}
        <div className="mb-3">
          <label className="text-xs text-[var(--jp-ui-font-color2)] mb-1 block">
            Budget Limit (USD)
          </label>
          <input
            type="number"
            step="0.01"
            className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
            value={
              config.usage_limit_usd === null ? '' : config.usage_limit_usd
            }
            onChange={e => {
              const val = e.target.value;
              handleChange(
                'usage_limit_usd',
                val === '' ? null : parseFloat(val)
              );
            }}
            placeholder="Unlimited"
            disabled={disabled || readonly}
          />
        </div>

        {/* Request Limit */}
        <div className="mb-3">
          <label className="text-xs text-[var(--jp-ui-font-color2)] mb-1 block">
            Request Limit
          </label>
          <input
            type="number"
            step="1"
            min="1"
            className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
            value={config.request_limit === null ? '' : config.request_limit}
            onChange={e => {
              const val = e.target.value;
              handleChange(
                'request_limit',
                val === '' ? null : parseInt(val, 10)
              );
            }}
            placeholder="(50 default)"
            disabled={disabled || readonly}
          />
          <p className="text-xs text-[var(--jp-ui-font-color3)] mt-1">
            Maximum number of requests allowed to the model.
          </p>
        </div>

        {/* Token Limits (Optional - if you want to add more) */}
        <div className="mb-3">
          <label className="text-xs text-[var(--jp-ui-font-color2)] mb-1 block">
            Total Tokens Limit
          </label>
          <input
            type="number"
            step="1000"
            className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
            value={
              config.total_tokens_limit === null
                ? ''
                : config.total_tokens_limit
            }
            onChange={e => {
              const val = e.target.value;
              handleChange(
                'total_tokens_limit',
                val === '' ? null : parseInt(val, 10)
              );
            }}
            placeholder="Unlimited"
            disabled={disabled || readonly}
          />
        </div>
      </div>

      {/* Toolcall Timeout */}
      <div className="mb-4">
        <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
          Tool Timeout (seconds, max=600)
        </label>
        <input
          type="number"
          min="1"
          max="600"
          className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
          value={config.tool_timeout || 300}
          onChange={e => handleChange('tool_timeout', parseInt(e.target.value))}
          disabled={disabled || readonly}
        />
      </div>

      {/* Backend Type */}
      <div className="mb-4">
        <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
          Backend Type
        </label>
        <select
          className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
          value={config.backend || 'LocalBackend'}
          onChange={e => handleChange('backend', e.target.value)}
          disabled={disabled || readonly}
        >
          {backendOptions.map(opt => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>

      {/* MLflow Instrumentation Section */}
      <div className="mb-4 space-y-3">
        {/* 1. Enable/Disable Toggle */}
        <label className="flex items-center space-x-2 cursor-pointer">
          <input
            type="checkbox"
            className="w-4 h-4 rounded border-[var(--jp-border-color2)] text-[var(--jp-brand-color1)] bg-[var(--jp-layout-color1)]"
            checked={!!config.enable_system_mlflow}
            onChange={e =>
              handleChange('enable_system_mlflow', e.target.checked)
            }
            disabled={disabled || readonly}
          />
          <span className="text-sm font-bold text-[var(--jp-ui-font-color1)]">
            MLflow Instrumentation Infra
          </span>
        </label>

        {/* 2. Detailed Configuration (Shown only when enabled) */}
        {config.enable_system_mlflow && (
          <div className="ml-6 space-y-2">
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <label className="text-xs font-semibold text-[var(--jp-ui-font-color2)]">
                  MLflow Tracking URI
                </label>
                <span className="inline-flex items-center gap-1">
                  <span
                    className="inline-block w-2 h-2 rounded-full"
                    style={{
                      backgroundColor: is_mlflow_active
                        ? 'var(--jp-success-color1)'
                        : 'var(--jp-error-color1)'
                    }}
                  />
                  <span
                    className="text-xs"
                    style={{
                      color: is_mlflow_active
                        ? 'var(--jp-success-color1)'
                        : 'var(--jp-error-color1)'
                    }}
                  >
                    {is_mlflow_active ? 'Active' : 'Inactive'}
                  </span>
                </span>
              </div>

              <div className="flex gap-2">
                {/* Tracking URI input field */}
                <input
                  type="text"
                  placeholder="http://127.0.0.1:5000"
                  className="flex-1 p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
                  value={config.mlflow_tracking_uri || ''}
                  onChange={e =>
                    handleChange('mlflow_tracking_uri', e.target.value)
                  }
                  disabled={disabled || readonly}
                />

                {/* Test Connection Button */}
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={
                    disabled || readonly || mlflowTestMutation.isPending
                  }
                  className="px-3 py-2 text-sm font-medium border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color2)] hover:bg-[var(--jp-layout-color3)] text-[var(--jp-ui-font-color1)] transition-colors disabled:opacity-50"
                >
                  {mlflowTestMutation.isPending ? 'Testing...' : 'Test'}
                </button>
              </div>
            </div>

            {/* Connection Success Feedback */}
            {mlflowTestMutation.isSuccess &&
              mlflowTestMutation.data?.status === 'success' && (
                <div className="text-xs p-2 rounded bg-green-500/15 text-green-600 border border-green-500/20">
                  {mlflowTestMutation.data.message ||
                    'Connection successful! MLflow is ready.'}
                </div>
              )}

            {/* Connection Error Feedback */}
            {(mlflowTestMutation.isError ||
              (mlflowTestMutation.isSuccess &&
                mlflowTestMutation.data?.status === 'error')) && (
              <div className="text-xs p-2 rounded bg-red-500/15 text-red-600 border border-red-500/20">
                {mlflowTestMutation.isError
                  ? mlflowTestMutation.error instanceof Error
                    ? mlflowTestMutation.error.message
                    : 'Connection failed.'
                  : mlflowTestMutation.data?.message}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default GlobalField;
