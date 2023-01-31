#!/bin/bash

path=$(pwd)
cd "$path/azure_function_timer_trigger_code"
tar --exclude="Readme.md" -cvf ../azure_function_timer_trigger_code.zip ./