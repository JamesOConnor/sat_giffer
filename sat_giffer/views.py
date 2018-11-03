from django.shortcuts import render


def leaflet_map(request):
    return render(request, 'leaflet_map.html')

def get_gif(request):
    body = request.POST('geometry')
    stack = make_gif(body)
    return stack