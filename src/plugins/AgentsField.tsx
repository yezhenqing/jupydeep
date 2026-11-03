import React, { useState, useCallback } from 'react';
import { FieldProps } from '@rjsf/utils';
import { useEngineCatalog } from '../hooks/useEngine';
import { AgentItem } from './agents/AgentItem';

interface IAgentsFormData {
  [agentName: string]: any;
}

const EMPTY_ARRAY: any[] = [];

const AgentsField: React.FC<FieldProps> = props => {
  const { schema, formData = {}, onChange, disabled, readonly } = props;

  const { data: engineData, isLoading } = useEngineCatalog();
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  const rootSchema = (props as any).registry?.rootSchema || schema;
  const agentConfigDefinition = rootSchema.definitions?.AgentConfig as any;

  const schemaCapabs =
    agentConfigDefinition?.properties?.capabilities?.items?.enum;

  const capablitiesEnum: string[] = schemaCapabs || [
    'include_todo',
    'include_filesystem',
    'include_subagents',
    'include_plan',
    'include_liteparse',
    'context_manager',
    'web_search',
    'web_fetch',
    'cost_tracking',
    'include_checkpoints',
    'include_teams',
    'include_memory'
  ];

  const llmsEnum = engineData?.payload?.llms || EMPTY_ARRAY;
  const skillsEnum = engineData?.payload?.skills || EMPTY_ARRAY;
  const mcpsEnum = engineData?.payload?.mcps || EMPTY_ARRAY;

  const engineAgents = engineData?.payload?.agents || {};
  const agentKeys = Object.keys(engineAgents);

  const toggleAgent = useCallback((agentName: string) => {
    setExpandedAgents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(agentName)) {
        newSet.delete(agentName);
      } else {
        newSet.add(agentName);
      }
      return newSet;
    });
  }, []);

  const checkboxDisabled = disabled || readonly;
  const checkboxClass = checkboxDisabled
    ? 'cursor-not-allowed'
    : 'cursor-pointer';
  const labelClass = checkboxDisabled ? 'cursor-not-allowed' : 'cursor-pointer';

  if (isLoading || !engineData) {
    return (
      <div className="p-5 text-center text-[var(--jp-ui-font-color2)] font-sans">
        Loading agent configurations...
      </div>
    );
  }

  if (agentKeys.length === 0) {
    return (
      <div className="mb-5 font-sans">
        <div className="flex justify-between items-center mb-4 pb-2 border-b-2 border-[var(--jp-border-color2)]">
          <h3 className="text-lg font-semibold text-[var(--jp-ui-font-color1)] m-0">
            Available Agents
          </h3>
        </div>
        <div className="p-10 text-center bg-[var(--jp-layout-color2)] border border-dashed border-[var(--jp-border-color2)] rounded-lg text-[var(--jp-ui-font-color2)]">
          No agents available
        </div>
      </div>
    );
  }

  return (
    <div className="mb-5 font-sans">
      {/* Header Controls */}
      <div className="flex justify-between items-center mb-4 pb-2 border-b-2 border-[var(--jp-border-color2)]">
        <div>
          <h3 className="text-lg font-semibold text-[var(--jp-ui-font-color1)] m-0">
            Available Agents
          </h3>
          <div className="text-sm text-[var(--jp-ui-font-color2)] mt-1">
            {agentKeys.length} agent(s)
          </div>
        </div>
        <button
          type="button"
          className="px-3 py-1 text-xs bg-[var(--jp-layout-color2)] border border-[var(--jp-border-color2)] rounded text-[var(--jp-ui-font-color1)] cursor-pointer hover:bg-[var(--jp-layout-color3)]"
          onClick={() =>
            setExpandedAgents(
              expandedAgents.size === agentKeys.length
                ? new Set()
                : new Set(agentKeys)
            )
          }
        >
          {expandedAgents.size === agentKeys.length
            ? 'Collapse All'
            : 'Expand All'}
        </button>
      </div>

      {/* Agent list */}
      {agentKeys.map(agentName => {
        const formAgentData = (formData as IAgentsFormData)[agentName] || {};
        const defaultAgentData = engineAgents[agentName] || {};

        return (
          <AgentItem
            key={agentName}
            agentName={agentName}
            formAgentData={formAgentData}
            defaultAgentData={defaultAgentData}
            isExpanded={expandedAgents.has(agentName)}
            onToggle={() => toggleAgent(agentName)}
            formData={formData as IAgentsFormData}
            onChange={onChange}
            disabled={disabled}
            readonly={readonly}
            isLLMsEmpty={llmsEnum.length === 0}
            is_mlflow_active={engineData?.payload?.is_mlflow_active || false}
            llmsEnum={llmsEnum}
            skillsEnum={skillsEnum}
            mcpsEnum={mcpsEnum}
            capablitiesEnum={capablitiesEnum}
            checkboxClass={checkboxClass}
            labelClass={labelClass}
          />
        );
      })}
    </div>
  );
};

export default AgentsField;
