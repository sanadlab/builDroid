import docker
from prettytable import PrettyTable

# Initialize Docker client
client = docker.from_env()

def list_images_and_containers():
    images = client.images.list()
    table = PrettyTable(["Image ID", "Repository", "Tag", "Container ID", "Container Name", "Status"])

    for image in images:
        image_id = image.id[:12]
        for tag in image.tags:
            repository, tag = tag.split(":") if ":" in tag else (tag, "<none>")
            containers = client.containers.list(all=True, filters={"ancestor": image.id})
            if containers:
                for container in containers:
                    table.add_row([image_id, repository, tag, container.id[:12], container.name, container.status])
            else:
                table.add_row([image_id, repository, tag, "N/A", "N/A", "N/A"])
    print(table)

def delete_container(container_id):
    try:
        container = client.containers.get(container_id)
        container.remove(force=True)
        print(f"Container {container_id} removed successfully.")
    except docker.errors.NotFound:
        print(f"Container {container_id} not found.")
    except Exception as e:
        print(f"Error: {str(e)}")

def delete_image(image_id):
    try:
        # Get all containers associated with this image
        containers = client.containers.list(all=True, filters={"ancestor": image_id})
        for container in containers:
            container.remove(force=True)
            print(f"Container {container.id[:12]} removed successfully.")

        # Attempt to remove the image
        client.images.remove(image_id, force=True)
        print(f"Image {image_id} removed successfully.")
    
    except docker.errors.APIError as e:
        if "image has dependent child images" in str(e):
            print(f"Error: The image {image_id} has dependent child images.")
            # Optionally list and remove child images
            handle_child_images(image_id)
        else:
            print(f"Error: {str(e)}")
    except docker.errors.ImageNotFound:
        print(f"Image {image_id} not found.")
    except Exception as e:
        print(f"Error: {str(e)}")

def handle_child_images(parent_image_id):
    # Find all child images of the given parent image
    images = client.images.list()
    child_images = []

    for image in images:
        if 'ParentId' in image.attrs and image.attrs['ParentId'] == parent_image_id:
            child_images.append(image)

    if child_images:
        print("\nThe following child images were found:")
        for image in child_images:
            print(f"Child Image ID: {image.id[:12]}")

        choice = input("\nDo you want to delete all child images? (y/n): ").strip().lower()

        if choice == 'y':
            for image in child_images:
                delete_image(image.id)
            # After deleting child images, try deleting the parent image again
            delete_image(parent_image_id)
        else:
            print("Operation aborted. The parent image cannot be deleted until the child images are removed.")
    else:
        print("No child images found. The image might have been removed already.")

def main():
    while True:
        print("\nDocker Image and Container Manager")
        list_images_and_containers()
        
        print("\nOptions:")
        print("1. Delete a container")
        print("2. Delete an image and all associated containers")
        print("3. Exit")
        
        choice = input("Enter your choice (1/2/3): ").strip()
        
        if choice == '1':
            container_id = input("Enter the container ID to delete: ").strip()
            delete_container(container_id)
        elif choice == '2':
            image_id = input("Enter the image ID to delete: ").strip()
            delete_image(image_id)
        elif choice == '3':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()