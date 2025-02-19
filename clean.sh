rm -rf experimental_setups/experiment_*
rm -rf logs/*
rm -rf execution_agent_workspace/*
touch execution_agent_workspace/readme
python3.10 remove_api_token.py
rm model_logging_temp.txt
> experimental_setups/experiments_list.txt