from django import forms

from .models import Cliente, Producto, TipoAfectacion, TipoDocumento, Unidad


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ('id_tipo_doc', 'nrodoc', 'razon_social', 'direccion')
        widgets = {
            'nrodoc': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 15}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'id_tipo_doc': forms.Select(attrs={'class': 'form-select'}),
        }


class ProductoForm(forms.ModelForm):
    afecto_igv = forms.BooleanField(
        required=False,
        label='Afecto a IGV',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = Producto
        fields = ('nombre', 'valor_unitario', 'codigo_sunat', 'id_unidad')
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'codigo_sunat': forms.TextInput(attrs={'class': 'form-control'}),
            'id_unidad': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            ta = self.instance.id_tipo_afectacion
            self.fields['afecto_igv'].initial = self._es_afecto_igv(ta)

    @staticmethod
    def _es_afecto_igv(tipo_afectacion) -> bool:
        if not tipo_afectacion:
            return True
        desc = (tipo_afectacion.descripcion or '').lower()
        codigo = (tipo_afectacion.codigo or '').strip()
        if codigo in ('10', '11', '12', '13', '14', '15', '16', '17'):
            return True
        return 'gravado' in desc or 'igv' in desc

    def save(self, commit=True):
        producto = super().save(commit=False)
        afecto = self.cleaned_data.get('afecto_igv', True)
        producto.id_tipo_afectacion = self._tipo_afectacion_por_flag(afecto)
        if commit:
            producto.save()
        return producto

    def _tipo_afectacion_por_flag(self, afecto: bool):
        if afecto:
            tipo = (
                TipoAfectacion.objects.filter(codigo='10').first()
                or TipoAfectacion.objects.filter(descripcion__icontains='gravado').first()
            )
        else:
            tipo = (
                TipoAfectacion.objects.filter(codigo='20').first()
                or TipoAfectacion.objects.filter(descripcion__icontains='exonerado').first()
                or TipoAfectacion.objects.filter(descripcion__icontains='inafecto').first()
            )
        return tipo or TipoAfectacion.objects.first()
