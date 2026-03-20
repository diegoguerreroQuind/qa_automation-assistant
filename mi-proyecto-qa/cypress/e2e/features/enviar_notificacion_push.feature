Feature: Probar enviar notificacion Push
  Scenario: Ejecutar exitosamente enviar notificacion Push
    Given que tengo los datos para 'enviar notificacion Push'
    When envío la petición hacia 'enviar notificacion Push'
    Then el código de respuesta para 'enviar notificacion Push' debe ser exitoso