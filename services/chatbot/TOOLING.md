# Chatbot Tool Inventory

This chatbot layer exposes controlled application functions only. It does not
execute arbitrary SQL, create SQLAlchemy sessions for the LLM, or bypass
existing authentication.

## `list_cases`

Function: `services.case.case_service.get_cases`

Inputs: none.

Output: list of case dictionaries plus count.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.

## `get_case`

Function: `services.case.case_service.get_case`

Inputs: `case_id`, or current context `case_id`.

Output: one case dictionary.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.

## `list_layers`

Function: `services.layer.layer_service.get_case_layers` when `case_id` is
available, otherwise `services.layer.layer_service.get_layers`.

Inputs: optional `case_id`, or current context `case_id`.

Output: list of layer dictionaries plus count.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.

## `get_layer`

Function: `services.layer.layer_service.get_layer`

Inputs: `layer_id`, or current context `layer_id` / `selected_layer_id`.

Output: one layer dictionary.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.

## `list_features`

Function: `services.feature.feature_service.get_layer_features` when `layer_id`
is available, otherwise `services.feature.feature_service.get_case_features`.

Inputs: optional `case_id`, optional `layer_id`, or current context.

Output: list of feature dictionaries/summaries plus count.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.

## `get_feature`

Function: `services.feature.feature_service.get_feature` when `feature_id` is
available, otherwise `services.feature.feature_service.get_feature_by_number`.

Inputs: `feature_id`, or `case_id`, `layer_id`, and `feature_number`; context can
provide selected feature/layer/case values.

Output: one feature dictionary.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.

## `get_comments`

Function: `services.comment.comment_service.get_layer_comments`

Inputs: `case_id` and `layer_id`, or current context.

Output: layer comments plus count.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.

## `get_comment_thread`

Function: `services.comment.comment_service.get_feature_comment_thread`

Inputs: `case_id`, `layer_id`, and `feature_number`, or current context.

Output: existing nested feature comment thread plus count.

Authorization: any authenticated user.

Side effects: none.

WebSocket events: none.
