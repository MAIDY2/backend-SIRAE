import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ImagenesService {
  private apiUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  /**
   * Sube o reemplaza la imagen de un plato específico mediante FormData.
   * El interceptor de autenticación global agregará el Token Bearer automáticamente.
   */
  subirImagenPlato(idPlato: number, file: File): Observable<{ imagen: string }> {
    const formData = new FormData();
    formData.append('imagen', file, file.name);
    
    // Las rutas del backend terminan en barra "/"
    return this.http.post<{ imagen: string }>(`${this.apiUrl}/platos/${idPlato}/imagen/`, formData);
  }
}