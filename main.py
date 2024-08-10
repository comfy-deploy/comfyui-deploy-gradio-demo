from comfydeploy import ComfyDeploy
import asyncio
import os
import gradio as gr
from PIL import Image
import requests
import dotenv
from io import BytesIO

dotenv.load_dotenv()

client = ComfyDeploy(bearer_auth=os.environ['API_KEY'])
deployment_id = os.environ['DEPLOYMENT_ID']

def get_gradio_component(class_type):
    component_map = {
        'ComfyUIDeployExternalText': gr.Textbox,
        'ComfyUIDeployExternalImage': gr.Image,
        'ComfyUIDeployExternalImageAlpha': gr.Image,
        'ComfyUIDeployExternalNumber': gr.Number,
        'ComfyUIDeployExternalNumberInt': gr.Number,
        'ComfyUIDeployExternalLora': gr.Textbox,
        'ComfyUIDeployExternalCheckpoint': gr.Textbox,
        'ComfyDeployWebscoketImageInput': gr.Image,
        'ComfyUIDeployExternalImageBatch': gr.File,
        'ComfyUIDeployExternalVideo': gr.Video,
        'ComfyUIDeployExternalBoolean': gr.Checkbox,
        'ComfyUIDeployExternalNumberSlider': gr.Slider,
    }
    return component_map.get(class_type, gr.Textbox)  # Default to Textbox if not found

# Function to update inputs
def get_inputs():
    res = client.deployment.get_input_definition(id=deployment_id)
    input_definitions = res.response_bodies
    gradio_inputs = []
    for input_def in input_definitions:
        component_class = get_gradio_component(input_def.class_type)
        
        kwargs = {
            "label": input_def.input_id,
            "value": input_def.default_value
        }
        
        print(kwargs)
        
        if input_def.class_type == 'ComfyUIDeployExternalNumberSlider':
            kwargs.update({
                "minimum": input_def.min_value,
                "maximum": input_def.max_value
            })
        elif input_def.class_type in ['ComfyUIDeployExternalImage', 'ComfyUIDeployExternalImageAlpha', 'ComfyDeployWebscoketImageInput']:
            kwargs["type"] = "filepath"
        elif input_def.class_type == 'ComfyUIDeployExternalImageBatch':
            kwargs["file_count"] = "multiple"
        elif input_def.class_type == 'ComfyUIDeployExternalNumberInt':
            kwargs["precision"] = 0
            
        # print(kwargs)
        
        gradio_inputs.append(component_class(**kwargs))
        
    return gradio_inputs, input_definitions

with gr.Blocks() as demo:
    with gr.Row():
        with gr.Column(scale=1):
            @gr.render()
            def update_inputs():
                inputs, input_definitions = get_inputs()
                submit_button = gr.Button("Submit")
                
                async def main(*args):
                    inputs = {input_def.input_id: arg for input_def, arg in zip(input_definitions, args)}
                    
                    for key, value in inputs.items():
                        if isinstance(value, list) and all(isinstance(url, str) for url in value):
                            inputs[key] = [requests.get(url).content for url in value]
                        elif isinstance(value, str) and value.startswith('http'):
                            inputs[key] = requests.get(value).content

                    res = await client.run.create_async(
                        request={
                            "deployment_id": deployment_id,
                            "inputs": inputs
                        })

                    images = []
                    text = ""
                    outputs = [
                        images,
                        text
                    ]
                    while True:
                        if res.object is not None:
                            res2 = await client.run.get_async(run_id=res.object.run_id)
                            print("checking ", res2.object.progress, res2.object.live_status)

                            if res2.object is not None and res2.object.status == "success":
                                # print(res2)
                                for output in res2.object.outputs:
                                    print(output.data.images)
                                    if output.data.images:
                                        urls = [image.url for image in output.data.images]
                                        for url in urls:
                                            response = requests.get(url)
                                            img = Image.open(BytesIO(response.content))
                                            outputs[0].append(img)
                                    elif output.data.text:
                                        print(output.data.text)
                                        outputs[1] += "\n\n" + "\n".join(output.data.text)
                                break
                        await asyncio.sleep(2)

                    return outputs
                
                submit_button.click(fn=main, inputs=inputs, outputs=output_components)
        
        with gr.Column(scale=1):
            output_components = [
                gr.Gallery(),
                gr.Textbox(label="Text Output")
            ]
            
if __name__ == "__main__":
    demo.launch(share=True)