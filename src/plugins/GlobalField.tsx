import React from 'react';
import { FieldProps } from '@rjsf/utils';
import { useEngineCatalog } from '../hooks/useEngine';

interface IGlobalConfig {
  default_agent?: string;
  default_model?: string;
  usage_limit_usd?: number | null;
  request_limit?: number | null;
  total_tokens_limit?: number | null;
  tool_timeout?: number;
  backend?: string;
}

const EMPTY_ARRAY: any[] = [];

const GlobalField: React.FC<FieldProps> = props => {
  const { formData = {}, onChange, disabled, readonly } = props;
  const config = formData as IGlobalConfig;

  const { data: engineData } = useEngineCatalog();
  const llmsEnum = engineData?.payload?.llms || EMPTY_ARRAY;
  const agentsEnum = Object.keys(engineData?.payload?.agents) || EMPTY_ARRAY;

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
    </div>
  );
};

export default GlobalField;
