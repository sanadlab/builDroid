rm -rf logs/*
rm -rf execution_agent_workspace/*
rm -rf search_logs/*
rm -rf parsable_logs/*
rm -rf problems_memory/*
rm -rf experimental_setups/experiment_*
touch execution_agent_workspace/readme
python3.10 remove_api_token.py
> experimental_setups/experiments_list.txt
rm model_logging_temp.txt