rm -rf logs/*
rm -rf execution_agent_workspace/*
rm -rf search_logs/*
rm -rf parsable_logs/*
rm -rf problems_memory/*
rm -rf experimental_setups/experiment_*
touch execution_agent_workspace/readme
source <(python3.10 api_token_reset.py)
> experimental_setups/experiments_list.txt