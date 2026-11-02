import React, { useState, useEffect, useRef } from 'react';
import { Debouncer } from '@lumino/polling';

interface IAgentConfigData {
  enabled?: boolean;
  description?: string;
  enable_mlflow?: boolean;
  mlflow_experiment_suffix?: string;
  is_mlflow_active?: boolean;
  model?: string;
  deep_mcps?: string[];
  capabilities?: string[];
  deep_skills?: string[];
}

interface IAgentsFormData {
  [agentName: string]: IAgentConfigData;
}

const EMPTY_ARRAY: any[] = [];

interface AgentItemProps {
  agentName: string;
  formAgentData: IAgentConfigData;
  defaultAgentData: any;
  isExpanded: boolean;
  onToggle: () => void;
  formData: IAgentsFormData;
  onChange: (formData: IAgentsFormData) => void;
  disabled?: boolean;
  readonly?: boolean;
  isLLMsEmpty: boolean;
  is_mlflow_active: boolean;
  llmsEnum: string[];
  skillsEnum: string[];
  mcpsEnum: string[];
  capablitiesEnum: string[];
  checkboxClass: string;
  labelClass: string;
}

export const AgentItem: React.FC<AgentItemProps> = ({
  agentName,
  formAgentData,
  defaultAgentData,
  isExpanded,
  onToggle,
  formData,
  onChange,
  disabled,
  readonly,
  isLLMsEmpty,
  is_mlflow_active,
  llmsEnum,
  skillsEnum,
  mcpsEnum,
  capablitiesEnum,
  checkboxClass,
  labelClass
}) => {
  const checkboxDisabled = disabled || readonly;

  const agentData: IAgentConfigData = {
    enabled: formAgentData?.enabled ?? defaultAgentData?.enabled ?? true,
    description:
      defaultAgentData?.description ?? formAgentData?.description ?? '',
    enable_mlflow:
      formAgentData?.enable_mlflow ?? defaultAgentData?.enable_mlflow ?? false,
    mlflow_experiment_suffix:
      defaultAgentData?.mlflow_experiment_suffix ??
      formAgentData?.mlflow_experiment_suffix ??
      '',
    model:
      formAgentData?.model ??
      defaultAgentData?.model ??
      defaultAgentData?.LLM ??
      '',
    deep_mcps:
      formAgentData?.deep_mcps ??
      defaultAgentData?.deep_mcps ??
      defaultAgentData?.MCPs ??
      EMPTY_ARRAY,
    capabilities:
      formAgentData?.capabilities ??
      defaultAgentData?.capabilities ??
      defaultAgentData?.features ??
      EMPTY_ARRAY,
    deep_skills:
      formAgentData?.deep_skills ??
      defaultAgentData?.deep_skills ??
      defaultAgentData?.skills ??
      EMPTY_ARRAY
  };

  const [localSuffix, setLocalSuffix] = useState(
    agentData.mlflow_experiment_suffix || ''
  );

  useEffect(() => {
    setLocalSuffix(agentData.mlflow_experiment_suffix || '');
  }, [agentData.mlflow_experiment_suffix]);

  const debouncerRef = useRef<Debouncer | null>(null);
  if (!debouncerRef.current) {
    debouncerRef.current = new Debouncer((val: string) => {
      onChange({
        ...formData,
        [agentName]: { ...agentData, mlflow_experiment_suffix: val }
      });
    }, 1200);
  }

  useEffect(() => {
    return () => {
      debouncerRef.current?.dispose?.();
    };
  }, []);

  const isEnabled = agentData.enabled === true;
  const isAgentDisabled = disabled || readonly || isLLMsEmpty;

  return (
    <div className="mb-4 border border-[var(--jp-border-color2)] rounded-lg overflow-hidden bg-[var(--jp-layout-color1)]">
      {/* Accordion Header */}
      <div
        className="flex justify-between items-center p-3 px-4 bg-[var(--jp-layout-color2)] cursor-pointer select-none"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <span
            className="text-sm transition-transform duration-200"
            style={{
              transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'
            }}
          >
            ▶
          </span>
          <span className="text-base font-semibold text-[var(--jp-ui-font-color1)]">
            {agentName}
          </span>
          <span
            className={`text-xs px-2 py-0.5 rounded-full ${
              isLLMsEmpty
                ? 'bg-[var(--jp-error-color1)] text-white'
                : isEnabled
                  ? 'bg-[var(--jp-success-color1)] text-white'
                  : 'bg-[var(--jp-error-color1)] text-white'
            }`}
          >
            {isLLMsEmpty
              ? 'Disabled (No LLM)'
              : isEnabled
                ? 'Enabled'
                : 'Disabled'}
          </span>
        </div>
      </div>

      <div className={isExpanded ? 'p-4' : 'hidden'}>
        <div className="mb-4">
          <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
            Enable Agent
          </label>
          <div className="flex items-center gap-1.5">
            <input
              type="checkbox"
              className={checkboxClass}
              checked={isLLMsEmpty ? false : agentData.enabled}
              onChange={e => {
                onChange({
                  ...formData,
                  [agentName]: { ...agentData, enabled: e.target.checked }
                });
              }}
              disabled={isAgentDisabled}
            />
            <label
              className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
            >
              Enable this agent
            </label>
          </div>
        </div>

        {/* Description */}
        <div className="mb-4">
          <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
            Description
          </label>
          <textarea
            className="w-full p-2 text-sm font-sans border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)] resize-y min-h-[120px]"
            defaultValue={agentData.description || ''}
            onBlur={e => {
              const newValue = e.target.value;
              const oldValue = agentData.description || '';
              if (newValue.trim() !== oldValue.trim()) {
                onChange({
                  ...formData,
                  [agentName]: { ...agentData, description: newValue }
                });
              }
            }}
            placeholder="Enter agent description..."
            disabled={disabled || readonly || isLLMsEmpty}
          />
        </div>

        {/* MLflow Section */}
        {is_mlflow_active && (
          <div className="mb-4 space-y-3 border-t border-[var(--jp-border-color2)] pt-4">
            <div className="space-y-1.5">
              <span className="text-sm font-bold text-[var(--jp-ui-font-color1)] block">
                Enable MLflow Tracing
              </span>
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-[var(--jp-border-color2)] text-[var(--jp-brand-color1)] bg-[var(--jp-layout-color1)] cursor-pointer"
                  checked={!!agentData.enable_mlflow}
                  onChange={e => {
                    onChange({
                      ...formData,
                      [agentName]: {
                        ...agentData,
                        enable_mlflow: e.target.checked
                      }
                    });
                  }}
                  disabled={disabled || readonly || isLLMsEmpty}
                />
                <span className="text-xs text-[var(--jp-ui-font-color2)]">
                  Activate tracking for this agent
                </span>
              </div>
            </div>

            {agentData.enable_mlflow && (
              <div className="ml-6 space-y-2 mt-3">
                <label className="text-xs font-semibold text-[var(--jp-ui-font-color2)] mb-1 block">
                  Experiment Suffix
                </label>
                <input
                  type="text"
                  placeholder="e.g. experiment-v1"
                  className="w-full p-2 text-sm border border-[var(--jp-border-color2)] rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)]"
                  value={localSuffix}
                  onChange={e => {
                    const val = e.target.value;
                    setLocalSuffix(val);
                    debouncerRef.current?.invoke(val);
                  }}
                  disabled={disabled || readonly || isLLMsEmpty}
                />
                <p className="text-xs text-[var(--jp-ui-font-color3)] mt-1">
                  Optional suffix appended to the experiment name. Resulting
                  format:
                  <code className="text-[var(--jp-ui-font-color2)] font-mono">
                    JupyDeep-{agentName}-&lt;suffix&gt;
                  </code>
                </p>
              </div>
            )}
          </div>
        )}

        {/* LLM Selection */}
        <div className="mb-4">
          <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
            Language Model (LLM)
          </label>
          {isLLMsEmpty ? (
            <div className="text-sm text-orange-500 italic">
              Not available. Please configure at least one functioning LLM.
            </div>
          ) : (
            <div className="flex flex-wrap gap-x-4 gap-y-2 mt-2">
              {llmsEnum.map((modelName: string) => (
                <div
                  key={modelName}
                  className="flex items-center gap-1.5 py-0.5"
                >
                  <input
                    type="radio"
                    name={`${agentName}-llm-selection`}
                    className={`${checkboxClass} rounded-full`}
                    checked={agentData.model === modelName}
                    onChange={e => {
                      if (e.target.checked) {
                        onChange({
                          ...formData,
                          [agentName]: { ...agentData, model: modelName }
                        });
                      }
                    }}
                    disabled={checkboxDisabled}
                  />
                  <label
                    className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                  >
                    {modelName}
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* MCP Selection */}
        <div className="mb-4">
          <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
            MCP Servers
          </label>
          <div className="flex flex-wrap gap-3 mt-2">
            {mcpsEnum.map((mcpName: string) => (
              <div key={mcpName} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  className={checkboxClass}
                  checked={(agentData.deep_mcps || []).includes(mcpName)}
                  onChange={e => {
                    const current = agentData.deep_mcps || [];
                    const newMCPs = e.target.checked
                      ? [...current, mcpName]
                      : current.filter(f => f !== mcpName);
                    onChange({
                      ...formData,
                      [agentName]: { ...agentData, deep_mcps: newMCPs }
                    });
                  }}
                  disabled={isAgentDisabled}
                />
                <label
                  className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                >
                  {mcpName}
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* Capabilities Selection */}
        <div className="mb-4">
          <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
            Capabilities
          </label>
          <div className="flex flex-wrap gap-3 mt-2">
            {capablitiesEnum.map(capab => (
              <div key={capab} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  className={checkboxClass}
                  checked={(agentData.capabilities || []).includes(capab)}
                  onChange={e => {
                    const current = agentData.capabilities || [];
                    const newCapabs = e.target.checked
                      ? [...current, capab]
                      : current.filter(f => f !== capab);
                    onChange({
                      ...formData,
                      [agentName]: { ...agentData, capabilities: newCapabs }
                    });
                  }}
                  disabled={isAgentDisabled}
                />
                <label
                  className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                >
                  {capab}
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* Skill Selection */}
        <div className="mb-4">
          <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
            Skills
          </label>
          <div className="flex flex-wrap gap-3 mt-2">
            {skillsEnum.map((skill: string) => (
              <div key={skill} className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  className={checkboxClass}
                  checked={(agentData.deep_skills || []).includes(skill)}
                  onChange={e => {
                    const current = agentData.deep_skills || [];
                    const newSkills = e.target.checked
                      ? [...current, skill]
                      : current.filter(s => s !== skill);
                    onChange({
                      ...formData,
                      [agentName]: { ...agentData, deep_skills: newSkills }
                    });
                  }}
                  disabled={isAgentDisabled}
                />
                <label
                  className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                >
                  {skill}
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom Summary */}
        {((agentData.capabilities?.length || 0) > 0 ||
          (agentData.deep_skills?.length || 0) > 0) && (
          <div className="mt-3 pt-3 border-t border-[var(--jp-border-color2)] text-xs text-[var(--jp-ui-font-color2)]">
            Summary: {agentData.capabilities?.length || 0} capability(ies) ·{' '}
            {agentData.deep_skills?.length || 0} skill(s)
          </div>
        )}
      </div>
    </div>
  );
};
