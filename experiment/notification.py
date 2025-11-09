import os
from pync import Notifier

# Get the absolute path to the avatar image
avatar_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'avatars', 'happy_cat.png'))

# Send notification with icon and click action to open the image
Notifier.notify(
    'Hello!',
    title='Test',
    contentImage=avatar_path,  # Display the avatar image in the notification
    open=f'file://{avatar_path}'  # Open the image when notification is clicked
)