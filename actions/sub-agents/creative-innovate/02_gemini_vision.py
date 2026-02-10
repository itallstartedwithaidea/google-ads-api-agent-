    # Add image if provided
    if image_url:
        img_data = download_image_as_base64(image_url)
        if 'error' in img_data:
            return {'status': 'error', 'message': f'Failed to load image: {img_data["error"]}'}
        parts.append(types.Part.from_bytes(
            data=base64.b64decode(img_data['data']),
            mime_type=img_data['mime_type']
        ))

    contents = [types.Content(role='user', parts=parts)]

    # Build config
    image_config = types.ImageConfig(aspect_ratio=api_ratio)
    if resolution and model_preference == 'nano_banana_pro':
        image_config = types.ImageConfig(aspect_ratio=api_ratio, image_size=resolution)

    gen_config = types.GenerateContentConfig(
        response_modalities=['IMAGE', 'TEXT'],
        image_config=image_config
    )

    # Add grounding if requested
    tools = None
    if use_grounding:
        tools = [types.Tool(google_search=types.GoogleSearch())]

    # Try models in fallback order
    model_order = ['nano_banana_pro', 'nano_banana', 'gemini_flash']
    if model_preference and model_preference in model_order:
        model_order = [model_preference] + [m for m in model_order if m != model_preference]

    last_error = None
    attempts = []

    for model_key in model_order:
        model_info = MODELS.get(model_key)
        if not model_info:
            continue

        try:
            response = client.models.generate_content(
                model=model_info['id'],
                contents=contents,
                config=gen_config
            )

            # Extract image from response
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        if part.inline_data.mime_type.startswith('image/'):
                            # Save to file
                            ext = mimetypes.guess_extension(part.inline_data.mime_type) or '.png'
                            filename = save_binary_file(part.inline_data.data, 'gemini_generated', ext.lstrip('.'))

                            text_response = None
                            for p in response.candidates[0].content.parts:
                                if hasattr(p, 'text') and p.text:
                                    text_response = p.text
                                    break

                            return {
                                'status': 'success',
                                'filename': filename,
                                'model': model_info['name'],
                                'model_icon': model_info['icon'],
                                'aspect_ratio': api_ratio,
                                'text_response': text_response,
                                'attempts': attempts + [{'model': model_info['name'], 'success': True}]
                            }

            attempts.append({'model': model_info['name'], 'success': False, 'reason': 'No image in response'})

        except Exception as e:
            last_error = str(e)
            attempts.append({'model': model_info['name'], 'success': False, 'reason': last_error})

    return {
        'status': 'error',
        'message': f'All models failed. Last error: {last_error}',
        'attempts': attempts
    }

# =============================================================================
# VIDEO GENERATION USING SDK - Based on Veo Studio reference
# =============================================================================

def generate_video_sdk(prompt, image_url=None, aspect_ratio='16:9', duration=8, 
                       resolution='720p', fast=False):
    """
    Generate video using Google GenAI SDK.
    Based on Veo Studio reference implementation.
    """
    api_key = get_api_key()
    if not api_key:
        return {'status': 'error', 'message': 'Gemini API key not configured'}

    client = genai.Client(api_key=api_key)

    model_key = 'veo_fast' if fast else 'veo'
    model_info = MODELS[model_key]

    # Validate aspect ratio for video (only 16:9 and 9:16 supported)
    if aspect_ratio not in ['16:9', '9:16']:
        aspect_ratio = '16:9'

    debug_info = {}

    try:
        # Build config matching Veo Studio pattern
        config = types.GenerateVideosConfig(
            number_of_videos=1,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

        # Prepare image if provided (for image-to-video)
        image_param = None
        if image_url:
            img_data = download_image_as_base64(image_url)
            if 'error' not in img_data:
                image_param = types.Image(
                    image_bytes=base64.b64decode(img_data['data']),
                    mime_type=img_data['mime_type']
                )
                debug_info['image_provided'] = True

        # Start video generation
        debug_info['model'] = model_info['id']
        debug_info['config'] = {'aspect_ratio': aspect_ratio, 'resolution': resolution}

        if image_param:
            operation = client.models.generate_videos(
                model=model_info['id'],
                prompt=prompt,
                image=image_param,
                config=config
            )
        else:
            operation = client.models.generate_videos(
                model=model_info['id'],
                prompt=prompt,
                config=config
            )

        debug_info['operation_started'] = True
        debug_info['operation_name'] = getattr(operation, 'name', 'unknown')

        # Poll until complete - matching Veo Studio pattern
        max_polls = 60  # 10 minutes max
        poll_count = 0

        while not operation.done and poll_count < max_polls:
            time.sleep(10)  # Wait 10 seconds between polls
            operation = client.operations.get(operation=operation)
            poll_count += 1

        debug_info['polls_completed'] = poll_count
        debug_info['operation_done'] = operation.done

        if not operation.done:
            return {
                'status': 'error',
                'message': 'Video generation timed out after 10 minutes',
                'model': model_info['name'],
                'debug': debug_info
            }

        # Check for error in operation
        if hasattr(operation, 'error') and operation.error:
            return {
                'status': 'error',
                'message': f'Operation error: {operation.error}',
                'model': model_info['name'],
                'debug': debug_info
            }

        # Extract video from response - inspect the structure
        debug_info['has_response'] = operation.response is not None

        if operation.response:
            response = operation.response
            debug_info['response_type'] = str(type(response))
            debug_info['response_attrs'] = [attr for attr in dir(response) if not attr.startswith('_')]

            # Try different ways to access the video
            generated_videos = None

            # Method 1: generated_videos attribute
            if hasattr(response, 'generated_videos'):
                generated_videos = response.generated_videos
                debug_info['access_method'] = 'generated_videos'

            # Method 2: videos attribute
            elif hasattr(response, 'videos'):
                generated_videos = response.videos
                debug_info['access_method'] = 'videos'

            # Method 3: result attribute
            elif hasattr(response, 'result'):
                result = response.result
                if hasattr(result, 'generated_videos'):
                    generated_videos = result.generated_videos
                    debug_info['access_method'] = 'result.generated_videos'

            debug_info['generated_videos_found'] = generated_videos is not None
            debug_info['generated_videos_count'] = len(generated_videos) if generated_videos else 0

            if generated_videos and len(generated_videos) > 0:
                video_obj = generated_videos[0]
                debug_info['video_obj_type'] = str(type(video_obj))
                debug_info['video_obj_attrs'] = [attr for attr in dir(video_obj) if not attr.startswith('_')]

                # Get the video data
                video_data = None
                video_uri = None

                # Check for video attribute with uri
                if hasattr(video_obj, 'video'):
                    inner_video = video_obj.video
                    debug_info['inner_video_type'] = str(type(inner_video))
                    if hasattr(inner_video, 'uri'):
                        video_uri = inner_video.uri
                        debug_info['video_uri'] = video_uri[:100] if video_uri else None

                # Check for direct uri
                elif hasattr(video_obj, 'uri'):
                    video_uri = video_obj.uri
                    debug_info['video_uri'] = video_uri[:100] if video_uri else None

                if video_uri:
                    # Fetch the video from URI
                    decoded_uri = unquote(video_uri)
                    # Check if key parameter already exists
                    if '?' in decoded_uri:
                        video_fetch_url = f"{decoded_uri}&key={api_key}"
                    else:
                        video_fetch_url = f"{decoded_uri}?key={api_key}"

                    debug_info['fetching_video'] = True
                    video_response = requests.get(video_fetch_url, timeout=120)
                    debug_info['video_response_status'] = video_response.status_code

                    if video_response.ok:
                        filename = save_binary_file(video_response.content, 'veo_video', 'mp4')
                        return {
                            'status': 'success',
                            'filename': filename,
                            'model': model_info['name'],
                            'model_icon': model_info['icon'],
                            'duration': duration,
                            'aspect_ratio': aspect_ratio,
                            'resolution': resolution,
                            'debug': debug_info
                        }
                    else:
                        return {
                            'status': 'error',
                            'message': f'Failed to download video: {video_response.status_code} - {video_response.text[:200]}',
                            'model': model_info['name'],
                            'debug': debug_info
                        }
                else:
                    return {
                        'status': 'error',
                        'message': 'Video object found but no URI available',
                        'model': model_info['name'],
                        'debug': debug_info
                    }
            else:
                return {
                    'status': 'error',
                    'message': 'No videos in response',
                    'model': model_info['name'],
                    'debug': debug_info
                }
        else:
            return {
                'status': 'error',
                'message': 'No response from operation',
                'model': model_info['name'],
                'debug': debug_info
            }

    except Exception as e:
        import traceback
        return {
            'status': 'error',
            'message': str(e),
            'model': model_info['name'],
            'traceback': traceback.format_exc(),
            'debug': debug_info
        }

# =============================================================================
# AI STUDIO MODE
# =============================================================================

def ai_studio_create(prompt, image_url=None, aspect_ratio='1:1', resolution='4K',
                     use_grounding=True, thinking_level='high', temperature=1.0):
    """Full AI Studio creative experience with all features."""
    full_prompt = DEFAULT_AI_INSTRUCTIONS + '\n\n' + prompt

    return generate_image_sdk(
        prompt=full_prompt,
        image_url=image_url,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        use_grounding=use_grounding,
        thinking_level=thinking_level,
        model_preference='nano_banana_pro'
    )

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run(action, **kwargs):
    """
    Gemini Nano Banana AI Studio v5.15.0 - Main entry point.
    Enhanced debug logging for video generation.

    Actions:
    - generate_image: Generate/edit image (prompt required, image_url optional)
    - resize_for_ratio: Resize image to aspect ratio (image_url, aspect_ratio required)
    - ai_studio_create: Full AI Studio experience with grounding & controls
    - generate_video: Create video with Veo 3.1 (prompt required, paid API key required)
    - check_ratio_compatible: Check if ratio works with Gemini
    - get_models: List available models
    - get_valid_ratios: List Gemini-compatible ratios
    """

    try:
        if action == 'generate_image':
            prompt = kwargs.get('prompt', '')
            image_url = kwargs.get('image_url')
            aspect_ratio = kwargs.get('aspect_ratio', '1:1')
            resolution = kwargs.get('resolution', '2K')
            model = kwargs.get('model', 'nano_banana_pro')
            custom_instructions = kwargs.get('custom_instructions', '')
            use_grounding = kwargs.get('use_grounding', False)

            full_prompt = DEFAULT_AI_INSTRUCTIONS + '\n\n' + prompt
            if custom_instructions:
                full_prompt += '\n\n' + custom_instructions

            return generate_image_sdk(
                prompt=full_prompt,
                image_url=image_url,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                use_grounding=use_grounding,
                model_preference=model
            )

        elif action == 'resize_for_ratio':
            image_url = kwargs.get('image_url')
            aspect_ratio = kwargs.get('aspect_ratio', '1:1')
            resolution = kwargs.get('resolution', '2K')
            model = kwargs.get('model', 'nano_banana_pro')
            custom_instructions = kwargs.get('custom_instructions', '')

            if not image_url:
                return {'status': 'error', 'message': 'image_url is required'}

            api_ratio = normalize_ratio(aspect_ratio)
            prompt = f"{DEFAULT_AI_INSTRUCTIONS}\n\nResize this image to {api_ratio} aspect ratio. Preserve all subjects and extend the background naturally where needed."
            if custom_instructions:
                prompt += f'\n\n{custom_instructions}'

            result = generate_image_sdk(
                prompt=prompt,
                image_url=image_url,
                aspect_ratio=api_ratio,
                resolution=resolution,
                model_preference=model
            )
            result['target_ratio'] = api_ratio
            return result

        elif action == 'ai_studio_create':
            return ai_studio_create(
                prompt=kwargs.get('prompt', ''),
                image_url=kwargs.get('image_url'),
                aspect_ratio=kwargs.get('aspect_ratio', '1:1'),
                resolution=kwargs.get('resolution', '4K'),
                use_grounding=kwargs.get('use_grounding', True),
                thinking_level=kwargs.get('thinking_level', 'high'),
                temperature=kwargs.get('temperature', 1.0)
            )

        elif action == 'generate_video':
            prompt = kwargs.get('prompt', '')
            image_url = kwargs.get('image_url')
            aspect_ratio = kwargs.get('aspect_ratio', '16:9')
            duration = kwargs.get('duration', 8)
            resolution = kwargs.get('resolution', '720p')
            fast = kwargs.get('fast', False)

            if not prompt:
                return {'status': 'error', 'message': 'prompt is required'}

            return generate_video_sdk(prompt, image_url, aspect_ratio, duration, resolution, fast)

        elif action == 'check_ratio_compatible':
            width = kwargs.get('width')
            height = kwargs.get('height')
            ratio_string = kwargs.get('ratio_string')

            if ratio_string:
                api_ratio = normalize_ratio(ratio_string)
                return {
                    'status': 'success',
                    'input': ratio_string,
                    'normalized': api_ratio,
                    'compatible': api_ratio in VALID_ASPECT_RATIOS
                }
            elif width and height:
                result = is_ratio_compatible(width, height)
                result['status'] = 'success'
                return result
            else:
                return {'status': 'error', 'message': 'Provide width+height or ratio_string'}

        elif action == 'get_models':
            return {
                'status': 'success',
                'models': {
                    key: {
                        'name': m['name'],
                        'icon': m['icon'],
                        'description': m['description'],
                        'max_resolution': m.get('max_resolution'),
                        'resolutions': m.get('resolutions'),
                        'aspect_ratios': m.get('aspect_ratios'),
                        'supports_grounding': m.get('supports_grounding', False),
                        'supports_thinking': m.get('supports_thinking', False)
                    }
                    for key, m in MODELS.items()
                },
                'image_models': ['nano_banana', 'nano_banana_pro', 'gemini_flash', 'imagen'],
                'video_models': ['veo', 'veo_fast'],
                'fallback_order': ['nano_banana_pro', 'nano_banana', 'gemini_flash', 'imagen']
            }

        elif action == 'get_valid_ratios':
            return {
                'status': 'success',
                'ratios': VALID_ASPECT_RATIOS,
                'tolerance': f'{RATIO_TOLERANCE * 100}%',
                'social_media': {
                    '1:1': 'Instagram Feed, Facebook, Profile pics',
                    '4:5': 'Instagram Portrait, Facebook Portrait',
                    '3:4': 'Instagram Tall (2025 grid)',
                    '9:16': 'Stories, Reels, TikTok, Shorts',
                    '16:9': 'YouTube, LinkedIn, Twitter/X',
                    '2:3': 'Pinterest Pins'
                },
                'video': ['16:9', '9:16']
            }

        else:
            return {
                'status': 'error',
                'message': f'Unknown action: {action}',
                'available_actions': [
                    'generate_image', 'resize_for_ratio', 'ai_studio_create',
                    'generate_video', 'check_ratio_compatible',
                    'get_models', 'get_valid_ratios'
                ]
            }

    except Exception as e:
        import traceback
        return {'status': 'error', 'message': str(e), 'action': action, 'traceback': traceback.format_exc()}
